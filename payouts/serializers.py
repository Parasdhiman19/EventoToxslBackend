from rest_framework import serializers
from .models import Payout


class PayoutSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='payout_number', read_only=True)
    payoutNumber = serializers.CharField(source='payout_number', read_only=True)
    date = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    grossTotal = serializers.SerializerMethodField()
    grossAmount = serializers.DecimalField(source='gross_amount', max_digits=12, decimal_places=2, read_only=True)
    fee = serializers.SerializerMethodField()
    feeDeducted = serializers.DecimalField(source='fee_deducted', max_digits=10, decimal_places=2, read_only=True)
    netAmount = serializers.SerializerMethodField()
    netDisbursed = serializers.SerializerMethodField()
    netDisbursedNumeric = serializers.DecimalField(source='net_disbursed', max_digits=12, decimal_places=2, read_only=True)
    method = serializers.SerializerMethodField()
    methodType = serializers.CharField(source='method_type', read_only=True)
    destinationAccount = serializers.SerializerMethodField()
    reference = serializers.CharField(source='utr_reference', read_only=True)
    utrReference = serializers.CharField(source='utr_reference', read_only=True)
    paypalBatchId = serializers.CharField(source='paypal_batch_id', read_only=True)
    failureReason = serializers.CharField(source='failure_reason', read_only=True)

    class Meta:
        model = Payout
        fields = (
            'id', 'payoutNumber', 'date', 'amount', 'grossTotal', 'grossAmount',
            'fee', 'feeDeducted', 'netAmount', 'netDisbursed', 'netDisbursedNumeric',
            'method', 'methodType', 'destinationAccount', 'reference', 'utrReference',
            'paypalBatchId', 'status', 'failureReason'
        )

    def get_date(self, obj):
        return obj.created_at.strftime('%b %d, %Y')

    def get_amount(self, obj):
        return f"${obj.gross_amount:,.2f}"

    def get_grossTotal(self, obj):
        return f"${obj.gross_amount:,.2f}"

    def get_fee(self, obj):
        return f"${obj.fee_deducted:,.2f}"

    def get_netAmount(self, obj):
        return f"${obj.net_disbursed:,.2f}"

    def get_netDisbursed(self, obj):
        return f"${obj.net_disbursed:,.2f}"

    def get_method(self, obj):
        if obj.destination_summary:
            return obj.destination_summary
        if obj.settlement_account:
            if obj.settlement_account.method_type == 'paypal':
                return f"PayPal ({obj.settlement_account.paypal_email})"
            return f"{obj.settlement_account.bank_name} {obj.settlement_account.account_number}"
        return "Direct Wire Settlement"

    def get_destinationAccount(self, obj):
        return self.get_method(obj)

