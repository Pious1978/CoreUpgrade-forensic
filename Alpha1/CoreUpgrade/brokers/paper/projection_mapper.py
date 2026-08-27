from .contracts import ExecutionReportContract

class GatewayProjectionMapper:
    @staticmethod
    def from_execution_report(report: ExecutionReportContract) -> BrokerResponseContract:
        return BrokerResponseContract(
            order_id=report.client_order_id,
            broker_order_id=report.broker_order_id,
            status=report.status,
            filled_quantity=report.filled_quantity,
            remaining_quantity=report.remaining_quantity,
            average_fill_price=report.average_fill_price,
            error_message=report.error_message,
            timestamp=report.timestamp,
            correlation_id=report.correlation_id,
            broker_name=report.broker_name
        )
