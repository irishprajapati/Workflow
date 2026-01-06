from .models import * 
def has_role(user, *roles):
    employee = getattr(user, 'employee_profile', None)
    if not employee:
        return False
    return employee.role in roles

LEAVE_VALIDATION_RULES = {
    "annual":    {"min_notice_days": 7,  "allow_past_start": False, "max_backdate_days": 0},
    "sick":      {"min_notice_days": 0,  "allow_past_start": True,  "max_backdate_days": 7},
    "casual":    {"min_notice_days": 1,  "allow_past_start": False, "max_backdate_days": 0},
    "maternity": {"min_notice_days": 30, "allow_past_start": True,  "max_backdate_days": 365},
    "paternity": {"min_notice_days": 14, "allow_past_start": False, "max_backdate_days": 0},
    "unpaid":    {"min_notice_days": 30, "allow_past_start": False, "max_backdate_days": 0},
}