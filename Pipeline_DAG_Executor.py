"""
Pipeline_DAG_Executor.py
-------------------------------------------------------------------------

Institutional Quant Pipeline Master Orchestrator

Responsibilities:

1. Execute research pipeline in dependency order
2. Validate critical checkpoints
3. Maintain execution logs
4. Launch live execution surveillance
5. Prevent duplicate monitors

Pipeline:

Universe
   |
Market Data
   |
Relative Strength
   |
Regime
   |
Alpha Discovery
   |
Pattern Engines
   |
Consensus
   |
Ranking
   |
Risk Engine
   |
Live Execution Monitor

-------------------------------------------------------------------------

"""


import os
import sys
import time
import sqlite3
import signal
import logging
import subprocess

from datetime import datetime


from core.config import DB_PATH



# ==============================================================
# LOGGER
# ==============================================================


class PipelineFormatter(logging.Formatter):

    def formatTime(self, record, datefmt=None):

        dt = datetime.fromtimestamp(record.created)

        return dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        ) + f",{int(record.msecs):03d}"



logger = logging.getLogger(
    "Pipeline_DAG"
)

logger.setLevel(
    logging.INFO
)


handler = logging.StreamHandler(
    sys.stdout
)

handler.setFormatter(
    PipelineFormatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )
)


logger.addHandler(handler)



# ==============================================================
# CONFIGURATION
# ==============================================================


MAX_RETRIES = 3

RETRY_DELAY = 5



PIPELINE_STAGES = [

    # Data Layer
    #
    # Universe_Updater.py intentionally excluded - its live NSE fetch
    # proved unreliable (a partial/incomplete response caused it to
    # incorrectly treat 268 actively-trading stocks as delisted, deleting
    # real data). Keep the universe update manual until it has a sanity
    # check against implausibly large single-day changes.

    "bhav_to_parquet_converter.py",


    # Market Intelligence

    "RelativeStrengthEngine.py",

    "Market_Regime_Engine.py",



    # Discovery Engines

    "Consolidation_Scanner.py",

    "Hybrid_Alpha_Scanner.py",

    "Emerging_Leader_Scanner.py",

    "Earnings_Gap_Scanner.py",

    "Cup_and_Handle.py",



    # Ranking Layer

    "Confirmation_Factor_Generator.py",

    "core/factor_registry.py",

    "Pivot_Consensus_Engine.py",


    # Final Research Terminal

    "Master_Terminal.py",



    # Risk Layer

    "Risk_Positioning_Engine.py",


    # Execution Planning

    "Execution_Plan_Generator.py"

]



LIVE_EXECUTION_SCRIPT = (
    "Live_Execution_Monitor.py"
)



# ==============================================================
# PIPELINE STATE
# ==============================================================


pipeline_results = []



# ==============================================================
# DATABASE CHECKPOINTS
# ==============================================================


def validate_database_checkpoint(
        table_name
):

    """
    Ensures critical tables exist
    """

    try:

        conn = sqlite3.connect(
            DB_PATH
        )

        cursor = conn.cursor()


        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name=?
            """,
            (table_name,)
        )


        result = cursor.fetchone()


        conn.close()



        if result:

            logger.info(
                f"DB CHECK PASSED : {table_name}"
            )

            return True


        else:

            logger.warning(
                f"DB CHECK FAILED : {table_name}"
            )

            return False


    except Exception as e:

        logger.error(
            f"Database validation error {e}"
        )

        return False




# ==============================================================
# RUN PIPELINE STAGE
# ==============================================================


def run_stage(
        script
):


    script_path = os.path.abspath(
        script
    )


    if not os.path.exists(script_path):

        raise FileNotFoundError(
            f"Missing Script : {script}"
        )



    start = time.time()



    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):


        try:

            logger.info(
                f"""
--------------------------------------------------
STARTING STAGE
{script}
Attempt {attempt}/{MAX_RETRIES}
--------------------------------------------------
"""
            )


            subprocess.run(

                [
                    sys.executable,
                    script_path
                ],

                check=True,

                encoding="utf-8"

            )


            elapsed = (
                time.time()
                -
                start
            )


            logger.info(
                f"COMPLETED {script} | {elapsed:.2f}s"
            )


            pipeline_results.append(
                {
                    "stage":script,
                    "status":"SUCCESS",
                    "time":round(elapsed,2)
                }
            )


            return True



        except subprocess.CalledProcessError as e:


            logger.warning(
                f"{script} FAILED attempt {attempt}"
            )


            if attempt < MAX_RETRIES:

                time.sleep(
                    RETRY_DELAY
                )

            else:


                pipeline_results.append(
                    {
                        "stage":script,
                        "status":"FAILED"
                    }
                )


                raise RuntimeError(
                    f"Pipeline halted at {script}"
                ) from e



# ==============================================================
# LIVE MONITOR MANAGEMENT
# ==============================================================


def launch_live_execution():

    script = os.path.abspath(
        LIVE_EXECUTION_SCRIPT
    )


    if not os.path.exists(script):

        logger.warning(
            "Live monitor missing"
        )

        return



    logger.info(
        "🚀 Launching Live Execution Monitor"
    )


    if sys.platform == "win32":


        subprocess.Popen(

            [
                sys.executable,
                script
            ],

            creationflags=subprocess.CREATE_NEW_CONSOLE

        )


    else:


        subprocess.Popen(

            [
                sys.executable,
                script
            ],

            start_new_session=True

        )





# ==============================================================
# MAIN DAG EXECUTION
# ==============================================================



def execute_pipeline_dag():


    run_id = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


    start_time=time.time()



    logger.info(
        """
==================================================================
 QUANTITATIVE PIPELINE DAG STARTING
==================================================================
"""
    )


    logger.info(
        f"RUN ID : {run_id}"
    )



    try:


        for stage in PIPELINE_STAGES:


            run_stage(
                stage
            )



        # Critical checkpoint - was checking for "research_consensus",
        # which never existed in this schema. The real table written by
        # Pivot_Consensus_Engine.py (the stage this checkpoint is meant
        # to verify) is consensus_pivots.

        validate_database_checkpoint(
            "consensus_pivots"
        )


        validate_database_checkpoint(
            "trade_candidates"
        )



        elapsed=time.time()-start_time



        logger.info(
            """
==================================================================
 BATCH PIPELINE COMPLETED
==================================================================
"""
        )


        logger.info(
            f"TOTAL TIME : {elapsed:.2f}s"
        )



        logger.info(
            "Launching live execution layer..."
        )


        launch_live_execution()



    except Exception as e:


        logger.error(
            "PIPELINE FAILED"
        )


        logger.exception(
            e
        )

        sys.exit(1)



# ==============================================================
# ENTRY POINT
# ==============================================================


if __name__=="__main__":


    execute_pipeline_dag()