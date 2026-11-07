from rest_framework import serializers

from apps.deposits.models import FixedDeposit, RecurringDeposit
from apps.loans.models import EMISchedule, LoanAccount
from apps.members.models import Member
from apps.savings.models import AccountTransaction, SavingsAccount
from apps.shares.models import ShareHolding


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = [
            'id',
            'member_no',
            'name',
            'father_name',
            'phone',
            'email',
            'dob',
            'address',
            'status',
            'join_date',
            'branch',
        ]
        read_only_fields = fields


class SavingsAccountSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.__str__', read_only=True)

    class Meta:
        model = SavingsAccount
        fields = [
            'id',
            'account_no',
            'member',
            'member_name',
            'account_type',
            'current_balance',
            'status',
            'opening_date',
            'branch',
        ]
        read_only_fields = fields


class AccountTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountTransaction
        fields = [
            'id',
            'account',
            'txn_type',
            'amount',
            'running_balance',
            'narration',
            'txn_date',
            'created_at',
            'voucher_no',
        ]
        read_only_fields = fields


class LoanAccountSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.__str__', read_only=True)

    class Meta:
        model = LoanAccount
        fields = [
            'id',
            'loan_no',
            'member',
            'member_name',
            'loan_product',
            'applied_amount',
            'approved_amount',
            'disbursed_amount',
            'outstanding_principal',
            'interest_rate',
            'tenure_months',
            'emi_amount',
            'status',
            'disbursed_date',
            'branch',
        ]
        read_only_fields = fields


class EMIScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EMISchedule
        fields = [
            'id',
            'loan',
            'installment_no',
            'due_date',
            'total_emi',
            'principal_component',
            'interest_component',
            'status',
            'paid_date',
            'paid_amount',
        ]
        read_only_fields = fields


class FixedDepositSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.__str__', read_only=True)

    class Meta:
        model = FixedDeposit
        fields = [
            'id',
            'fd_no',
            'member',
            'member_name',
            'deposit_amount',
            'interest_rate',
            'tenure_days',
            'maturity_date',
            'maturity_amount',
            'status',
            'start_date',
            'branch',
        ]
        read_only_fields = fields


class RecurringDepositSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.__str__', read_only=True)

    class Meta:
        model = RecurringDeposit
        fields = [
            'id',
            'rd_no',
            'member',
            'member_name',
            'monthly_installment',
            'interest_rate',
            'tenure_months',
            'maturity_date',
            'maturity_amount',
            'status',
            'start_date',
            'branch',
        ]
        read_only_fields = fields


class ShareHoldingSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.__str__', read_only=True)

    class Meta:
        model = ShareHolding
        fields = [
            'id',
            'member',
            'member_name',
            'share_count',
            'face_value_per_share',
            'total_amount',
            'status',
            'purchase_date',
            'certificate_no',
        ]
        read_only_fields = fields
