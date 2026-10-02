"""Exercise the actual Spark transforms without requiring AWS Glue libraries.

Run: python scripts/test-lab2-local.py
Dependencies: pyspark 3.5.x, Java 8/11/17. AWS Glue 4 uses Spark 3.3.
Only top-level imports of AWS Glue are excluded; all function bodies are unchanged.
"""
import ast
from pathlib import Path
from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parents[1]


def load_functions(filename):
    tree = ast.parse((ROOT / "glue-scripts" / filename).read_text())
    tree.body = [node for node in tree.body
                 if not (isinstance(node, ast.ImportFrom)
                         and (node.module or "").startswith("awsglue"))
                 and not isinstance(node, ast.If)]
    namespace = {"__name__": "test_subject"}
    exec(compile(tree, filename, "exec"), namespace)
    return namespace


spark = (SparkSession.builder.master("local[1]").appName("northstar-lab2-tests")
         .config("spark.driver.memory", "512m")
         .config("spark.sql.shuffle.partitions", "2")
         .config("spark.sql.ansi.enabled", "false")
         .config("spark.sql.legacy.timeParserPolicy", "CORRECTED")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
t = load_functions("transform.py")
f = load_functions("feature_engineer.py")

try:
    raw = spark.sql("""
      SELECT * FROM VALUES
      (' a ', ' c1 ', '04/01/2026', '10', '2', 'cash', 'online', 'ONLINE', 'food'),
      ('a', 'c1', '2026-04-01', '10', '2', 'cash', 'online', 'ONLINE', 'food'),
      ('b', 'c1', '2026-03-02', '', '', '', 'store', 's1', ''),
      ('c', 'c2', '2025-04-01', '30', '4', 'cash', 'store', 's1', 'food'),
      ('d', 'c1', '2026-04-02', '9999', '1', 'cash', 'store', 's1', 'food'),
      ('e', 'c2', '2026-07-01', '9999', '1', 'cash', 'store', 's1', 'food'),
      ('f', ' ', '2026-04-01', '20', '2', 'cash', 'store', 's1', 'food')
      AS t(transaction_id,customer_id,purchase_date,order_value,num_items,
           payment_method,channel,store_id,product_category)
    """)
    typed = t["cast_types"](raw)
    assert typed.count() == 6
    assert typed.filter("purchase_date IS NULL").count() == 0
    cleaned = t["deduplicate"](t["impute_nulls"](typed)).cache()
    assert cleaned.count() == 5
    missing = cleaned.filter("transaction_id = 'b'").first()
    assert missing.order_value == 30.0 and missing.num_items == 2
    assert missing.product_category == "unknown"
    history, holdout = f["split_windows"](cleaned)
    assert history.count() == 3 and holdout.count() == 1
    features = f["attach_churn_label"](f["compute_rfm_features"](history), holdout)
    rows = {r.customer_id: r for r in features.collect()}
    assert rows["c1"].total_lifetime_value == 40.0  # no future 9999 order
    assert rows["c1"].purchase_frequency_30d == 1.0  # excludes T - 30
    assert rows["c1"].category_diversity_score == 0.125
    assert rows["c1"].churn_label == 0 and rows["c2"].churn_label == 1
    assert rows["c2"].avg_basket_size_6m == 0.0
    tiers = spark.sql("SELECT * FROM VALUES (499.0), (500.0), (2000.0), (5000.0) AS t(total_lifetime_value)")
    assert [r.loyalty_tier for r in f["assign_loyalty_tier"](tiers).collect()] == ["Bronze", "Silver", "Gold", "Platinum"]
    print("PASS: cleanup, median imputation, transaction grain, temporal boundaries, no future leakage, empty recent window, tier thresholds")

    sample = spark.read.option("header", True).csv(str(ROOT / "northstar-raw-sample.csv"))
    processed = t["deduplicate"](t["impute_nulls"](t["cast_types"](sample))).cache()
    assert processed.filter("purchase_date IS NULL OR customer_id IS NULL").count() == 0
    history, holdout = f["split_windows"](processed)
    result = f["attach_churn_label"](f["compute_churn_proxy"](
        f["assign_loyalty_tier"](f["compute_rfm_features"](history))), holdout).cache()
    from pyspark.sql import functions as F
    from functools import reduce
    assert result.filter(reduce(lambda a, b: a | b, [F.col(c).isNull() for c in result.columns])).count() == 0
    assert result.count() == result.select("customer_id").distinct().count()
    assert result.filter("churn_risk_score < 0 OR churn_risk_score > 1").count() == 0
    assert result.select("churn_risk_score").distinct().count() > 3
    rate = result.agg(F.avg("churn_label")).first()[0]
    assert 0.15 <= rate <= 0.30
    assert {r.loyalty_tier for r in result.select("loyalty_tier").distinct().collect()} == {"Bronze", "Silver", "Gold", "Platinum"}
    print(f"PASS: full sample: {sample.count()} raw, {processed.count()} processed, {result.count()} customers, churn {rate:.2%}")
finally:
    spark.stop()
