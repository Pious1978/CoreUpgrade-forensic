import concurrent.futures
import logging
import time
from core.audit_config import config
from core.audit_registry import registry
from core.lifecycle import LifecycleHooks
from core.exceptions import AuditTimeoutError

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """DAG-aware execution engine enforcing timeouts, retries, and layer sequencing."""

    def __init__(self, context, lifecycle: LifecycleHooks = None):
        self.context = context
        self.lifecycle = lifecycle or LifecycleHooks()

    def run_audits(self) -> list:
        self.lifecycle.before_all(self.context)
        layers = registry.get_execution_layers()
        all_results = []
        order_counter = 0

        for layer_idx, layer in enumerate(layers):
            layer_results = []

            if config.execution.parallel_execution and len(layer) > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=config.execution.max_parallel_workers) as executor:
                    future_to_mod = {
                        executor.submit(self._execute_single_module, name, module_cls, metadata, order_counter + i): name
                        for i, (name, module_cls, metadata) in enumerate(layer)
                    }
                    timeout_sec = config.execution.default_timeout
                    for future in concurrent.futures.as_completed(future_to_mod):
                        mod_name = future_to_mod[future]
                        try:
                            res, err = future.result(timeout=timeout_sec)
                            if res:
                                layer_results.extend(res)
                            if err:
                                self.context.record_error(mod_name, str(err))
                        except concurrent.futures.TimeoutError:
                            timeout_err = AuditTimeoutError(f"Module '{mod_name}' exceeded timeout of {timeout_sec}s.")
                            logger.error(str(timeout_err))
                            self.context.telemetry.metrics[mod_name].timeouts += 1
                            self.lifecycle.on_timeout(mod_name, self.context)
                            self.context.record_error(mod_name, str(timeout_err))
                        except Exception as e:
                            logger.exception(f"Module '{mod_name}' failed in layer {layer_idx}: {e}")
                            self.context.record_error(mod_name, str(e))
            else:
                for i, (name, module_cls, metadata) in enumerate(layer):
                    res, err = self._execute_single_module(name, module_cls, metadata, order_counter + i)
                    if res:
                        layer_results.extend(res)
                    if err:
                        self.context.record_error(name, str(err))

            order_counter += len(layer)
            all_results.extend(layer_results)

        for r in all_results:
            self.context.add_result(r)

        return all_results

    def _execute_single_module(self, name: str, module_cls, metadata, execution_order: int):
        self.lifecycle.before_module(name, self.context)
        start_tuple = self.context.telemetry.start_module(name)
        self.context.telemetry.metrics[name].execution_order = execution_order

        retries = 0
        max_retries = config.execution.max_retries
        last_error = None

        while retries <= max_retries:
            try:
                instance = module_cls()
                results = instance.execute(self.context)
                res_list = results if isinstance(results, list) else [results]
                
                self.context.telemetry.end_module(name, start_tuple, retries=retries)
                self.lifecycle.after_module(name, res_list, self.context)
                return res_list, None
            except Exception as e:
                last_error = e
                retries += 1
                if retries <= max_retries:
                    self.lifecycle.on_retry(name, retries, e)
                    time.sleep(config.execution.retry_backoff * retries)
                else:
                    self.context.telemetry.end_module(name, start_tuple, retries=retries-1, exception=str(e))
                    self.lifecycle.on_failure(name, e, self.context)

        return [], last_error
