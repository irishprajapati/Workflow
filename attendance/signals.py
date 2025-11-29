from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.conf import settings
from .models import Employee, User, AttendanceRecord
from datetime import datetime
from django.utils import timezone

@receiver(post_save,sender = User)
def create_employee_for_user(sender, instance, created, **kwargs):
    if created and instance.role =='EMPLOYEE':
        Employee.objects.create(user=instance)
@receiver(pre_save, sender=AttendanceRecord)
def auto_checkout(sender, instance, **kwargs):
    if not instance.check_out and instance.check_in:
        #check if current time is past shift end
        dept = instance.employee.department
        if dept:
            shift_end = datetime.combine(instance.date, dept.work_end_time)
            now = timezone.now()
            if now>shift_end:
                instance.check_out = shift_end
                instance.is_auto_checkout=True

