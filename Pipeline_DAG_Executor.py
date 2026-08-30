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


def get_current_regime():
    """
    Reads the real, current regime written by Market_Regime_Engine.py
    (which runs as the first stage below, before this function is
    called for the discovery-engine stages further down). Falls back to
    NEUTRAL only if genuinely no regime data exists yet - matches the
    same fallback convention already used in Risk_Positioning_Engine.py
    and Live_Execution_Monitor.py.
    """

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT regime FROM market_regime ORDER BY date DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()

        if row is None:
            return "NEUTRAL"

        return row[0]

    except Exception:
        return "NEUTRAL"



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



PRE_REGIME_STAGES = [

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

]


# Bullish continuation setups (a stock about to break out of a tight
# base) - genuinely suited to trending/neutral/recovering markets, but
# these patterns are far less reliable when the broader market itself
# is falling.
BULLISH_DISCOVERY_STAGES = [

    "Consolidation_Scanner.py",

    "Hybrid_Alpha_Scanner.py",

    "Emerging_Leader_Scanner.py",

    "Earnings_Gap_Scanner.py",

    "Cup_and_Handle.py",

]


# Deep-pullback value/mean-reversion setups - the fundamentally
# different signal type genuinely suited to BEAR/DISTRIBUTION regimes,
# where the bullish continuation scanners above are chasing a pattern
# that doesn't hold up in a falling market. Kept separate rather than
# run alongside the bullish scanners, matching Alpha1's own real,
# working precedent (their Bear_Market_Scanner.py also produces its own
# separate output, not merged into the same momentum pipeline).
BEAR_REGIME_DISCOVERY_STAGES = [

    "Bear_Market_Scanner.py",

]


POST_DISCOVERY_STAGES = [

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


def run_stage_isolated(script):
    """
    Real, discovered vulnerability: run_stage() raises after exhausting
    retries, and that exception propagates all the way up - meaning a
    single crashed scanner would previously halt the ENTIRE remaining
    pipeline (the other 4 scanners, Master_Terminal.py, Risk_
    Positioning_Engine.py, everything), even though the other scanners
    are genuinely independent of each other and would have worked fine.

    Used only for the discovery-engine scanners specifically - NOT for
    pre-regime or post-discovery stages, which have real sequential
    dependencies where halting on failure is actually correct (a broken
    Master_Terminal.py genuinely should stop Risk_Positioning_Engine.py
    from running on bad input).

    Adapted from the real EngineResult/registry pattern found in Alpha1
    (Standard_Engine_Types.py + Engine_Registry.py) - a uniform result
    shape with per-engine error isolation, applied here at the scanner-
    stage level rather than the per-stock level, matching how our real
    scanners are actually structured (each a standalone script writing
    to its own table, not a per-stock evaluate() function).

    Returns a uniform result dict rather than raising, so the caller
    can continue to the next scanner and report a clear summary at the
    end of the cycle.
    """

    start = time.time()

    try:
        run_stage(script)

        return {
            "scanner": script,
            "verdict": "SUCCESS",
            "execution_time_s": round(time.time() - start, 2),
            "commentary": "Completed normally.",
        }

    except Exception as e:

        logger.warning(f"[ISOLATED] {script} failed - continuing to the next scanner. Error: {e}")

        return {
            "scanner": script,
            "verdict": "ERROR",
            "execution_time_s": round(time.time() - start, 2),
            "commentary": f"Crash: {e}",
        }


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


        for stage in PRE_REGIME_STAGES:

            run_stage(
                stage
            )


        # Market_Regime_Engine.py just ran above as part of
        # PRE_REGIME_STAGES, so this reads today's genuinely fresh
        # regime, not a stale value from a previous run.
        current_regime = get_current_regime()

        logger.info(
            f"Current regime: {current_regime}"
        )

        if current_regime in ("BEAR", "DISTRIBUTION"):

            logger.info(
                "Regime is BEAR/DISTRIBUTION - running Bear_Market_Scanner.py "
                "instead of the bullish continuation scanners this cycle."
            )

            discovery_stages = BEAR_REGIME_DISCOVERY_STAGES

        else:

            discovery_stages = BULLISH_DISCOVERY_STAGES


        scanner_results = []

        for stage in discovery_stages:

            result = run_stage_isolated(stage)
            scanner_results.append(result)

        logger.info("SCANNER STAGE SUMMARY")
        for r in scanner_results:
            logger.info(f"  {r['verdict']:<8} {r['scanner']:<35} "
                        f"{r['execution_time_s']}s  {r['commentary']}")

        failed_scanners = [r for r in scanner_results if r["verdict"] == "ERROR"]
        if failed_scanners:
            logger.warning(f"{len(failed_scanners)} of {len(scanner_results)} scanners failed this cycle - "
                            f"continuing with whatever candidates the rest produced.")

        for stage in POST_DISCOVERY_STAGES:

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