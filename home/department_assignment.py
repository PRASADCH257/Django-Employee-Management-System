import re

from django.db.models import Q


DEPARTMENT_ALIASES = {
    'HR': ('HR', 'HR (Human Resources)'),
    'DEVELOPMENT': ('DEVELOPMENT', 'Development'),
    'TESTING_QA': (
        'TESTING_QA',
        'Testing',
        'TESTING',
        'testing-qa',
        'testing_qa',
    ),
    'DATABASE_ADMINISTRATION': (
        'DATABASE_ADMINISTRATION',
        'Database Administration',
        'database_administration',
        'database-administration',
    ),
    'IT_SUPPORT': (
        'IT_SUPPORT',
        'IT Support',
        'it_support',
        'it-support',
    ),
}

ROLE_DEPARTMENT_MAP = {
    'hr': 'HR',
    'hr executive': 'HR',
    'hr officer': 'HR',
    'developer': 'DEVELOPMENT',
    'python developer': 'DEVELOPMENT',
    'software developer': 'DEVELOPMENT',
    'backend developer': 'DEVELOPMENT',
    'frontend developer': 'DEVELOPMENT',
    'full stack developer': 'DEVELOPMENT',
    'software engineer': 'DEVELOPMENT',
    'tester': 'TESTING_QA',
    'qa': 'TESTING_QA',
    'qa engineer': 'TESTING_QA',
    'software tester': 'TESTING_QA',
    'test engineer': 'TESTING_QA',
    'dba': 'DATABASE_ADMINISTRATION',
    'admin': 'DATABASE_ADMINISTRATION',
    'database administration': 'DATABASE_ADMINISTRATION',
    'database administrator': 'DATABASE_ADMINISTRATION',
    'database admin': 'DATABASE_ADMINISTRATION',
    'db admin': 'DATABASE_ADMINISTRATION',
    'db administrator': 'DATABASE_ADMINISTRATION',
    'sql developer': 'DATABASE_ADMINISTRATION',
    'database engineer': 'DATABASE_ADMINISTRATION',
    'it support': 'IT_SUPPORT',
    'it technician': 'IT_SUPPORT',
    'technical support': 'IT_SUPPORT',
    'system administrator': 'IT_SUPPORT',
}

DEPARTMENT_CODE_BY_ALIAS = {
    ' '.join(alias.casefold().split()): code
    for code, aliases in DEPARTMENT_ALIASES.items()
    for alias in aliases
}


def _normalize(value):
    return ' '.join((value or '').casefold().split())


def _normalized_value_pattern(values):
    phrases = []
    for value in values:
        words = _normalize(value).split()
        phrases.append(r'\s+'.join(re.escape(word) for word in words))
    return r'^\s*(?:' + '|'.join(phrases) + r')\s*$'


DEPARTMENT_PATTERNS_BY_CODE = {
    code: _normalized_value_pattern(aliases)
    for code, aliases in DEPARTMENT_ALIASES.items()
}
ROLE_PATTERNS_BY_DEPARTMENT = {
    code: _normalized_value_pattern(
        role for role, mapped_code in ROLE_DEPARTMENT_MAP.items()
        if mapped_code == code
    )
    for code in DEPARTMENT_ALIASES
}


def resolve_employee_department(employee):
    if _normalize(employee.account_type) != 'employee':
        return None

    department = _normalize(employee.department)
    if department:
        return DEPARTMENT_CODE_BY_ALIAS.get(department)

    return ROLE_DEPARTMENT_MAP.get(_normalize(employee.role))


def department_assignment_filter(department_code):
    department_is_blank = (
        Q(department__isnull=True)
        | Q(department__regex=r'^\s*$')
    )

    return Q(
        department__iregex=DEPARTMENT_PATTERNS_BY_CODE[department_code]
    ) | (
        department_is_blank
        & Q(role__iregex=ROLE_PATTERNS_BY_DEPARTMENT[department_code])
    )
