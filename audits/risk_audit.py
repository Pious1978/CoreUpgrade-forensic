from core.config import MAX_STOP_ATR


def audit_risk(df, schema):

    result = {
        "layer": "Risk",
        "status": "PASS",
        "score": 100,
        "details": []
    }


    pivot_col = schema["pivot"]
    stop_col = schema["stop_loss"]
    atr_col = schema["atr_14"]


    invalid = df[
        (df[stop_col] >= df[pivot_col]) |
        (
            df[stop_col] <
            df[pivot_col] -
            (MAX_STOP_ATR * df[atr_col])
        )
    ]


    for _, row in invalid.iterrows():

        result["details"].append(
            {
                "symbol": row["ticker"],
                "reason": "Invalid stop placement",
                "severity": "ERROR"
            }
        )


    if len(invalid):

        result["status"] = "ERROR"

        result["score"] = max(
            0,
            100 - (len(invalid)/len(df))*100
        )


    return result
