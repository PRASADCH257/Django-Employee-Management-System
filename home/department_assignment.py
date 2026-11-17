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


def department_assignment_filter(department_code):
    return Q(department__iregex=DEPARTMENT_PATTERNS_BY_CODE[department_code])


def resolve_employee_department(employee):
    return DEPARTMENT_CODE_BY_ALIAS.get(_normalize(employee.department))
