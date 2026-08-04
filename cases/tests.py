from django.test import TestCase

from Bank.models import Bank
from cases.models import Case, CaseType


class ChildCaseNumberGenerationTests(TestCase):
    def test_generate_unique_child_case_number_skips_existing_case_numbers(self):
        bank = Bank.objects.create(name='Test Bank')
        case_type = CaseType.objects.create(name='Test Case Type')

        parent = Case.objects.create(
            applicant_name='Parent Applicant',
            case_number='PARENT-1',
            bank=bank,
            case_type=case_type,
            status='pending',
        )

        Case.objects.create(
            applicant_name='Child 1',
            case_number='PARENT-1-2',
            bank=bank,
            case_type=case_type,
            status='pending',
            parent_case=parent,
        )
        Case.objects.create(
            applicant_name='Child 2',
            case_number='PARENT-1-3',
            bank=bank,
            case_type=case_type,
            status='pending',
            parent_case=parent,
        )
        Case.objects.create(
            applicant_name='Existing Case',
            case_number='PARENT-1-4',
            bank=bank,
            case_type=case_type,
            status='pending',
        )

        generated = Case.generate_unique_child_case_number(parent)

        self.assertEqual(generated, 'PARENT-1-5')
