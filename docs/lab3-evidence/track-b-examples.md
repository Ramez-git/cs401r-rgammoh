# Track B examples and observed failures

These five profiles were selected by the Task 1 model, not invented for the demo.
Category histories use only pre-cutoff transactions. Every offer is conditional on verified eligibility.

## Successful example 1: CUST-10006857

Profile:
```json
{
  "customer_id": "CUST-10006857",
  "loyalty_tier": "Bronze",
  "days_since_last_purchase": 305.0,
  "total_lifetime_value": 158.6,
  "avg_order_value": 79.3,
  "category_diversity_score": 0.125,
  "online_to_store_ratio": 0.0,
  "churn_probability": 0.98665756,
  "top_categories": [
    "Grocery"
  ],
  "category_source": "Lab 2 processed transactions on or before 2026-04-01, ranked by purchase count"
}
```

Generated offer:

Explore our Grocery category. If your account confirms Bronze status, you can earn 1 point per $1 of qualifying merchandise spend. Browse the selection and check your account before purchasing.

Retrieved chunk IDs: POL-LOY-011-s09-c01, POL-LOY-011-s06-c01, POL-LOY-011-s02-c01, POL-SHP-007-s02-c01, POL-RET-004-s11-c01, POL-RET-004-s06-c01, POL-SHP-007-s07-c01, POL-LOY-011-s11-c01

Safe copy fallback used: True. The policy incentive is rendered from retrieved evidence.

## Successful example 2: CUST-10009161

Profile:
```json
{
  "customer_id": "CUST-10009161",
  "loyalty_tier": "Silver",
  "days_since_last_purchase": 206.0,
  "total_lifetime_value": 654.03,
  "avg_order_value": 93.4329,
  "category_diversity_score": 0.25,
  "online_to_store_ratio": 0.1429,
  "churn_probability": 0.9840625,
  "top_categories": [
    "Apparel",
    "Outdoor"
  ],
  "category_source": "Lab 2 processed transactions on or before 2026-04-01, ranked by purchase count"
}
```

Generated offer:

Explore our Outdoor collection and discover gear that complements your Apparel purchases. If your account confirms Silver status, you can earn 1.25 points per $1 of qualifying merchandise spend. Browse your account to see what's waiting for you and check your current rewards balance.

Retrieved chunk IDs: POL-LOY-011-s09-c01, POL-LOY-011-s06-c01, POL-LOY-011-s02-c01, POL-SHP-007-s02-c01, POL-RET-004-s11-c01, POL-RET-004-s06-c01, POL-SHP-007-s07-c01, POL-LOY-011-s11-c01

Safe copy fallback used: False. The policy incentive is rendered from retrieved evidence.

## Successful example 3: CUST-10009715

Profile:
```json
{
  "customer_id": "CUST-10009715",
  "loyalty_tier": "Gold",
  "days_since_last_purchase": 258.0,
  "total_lifetime_value": 4244.73,
  "avg_order_value": 385.8845,
  "category_diversity_score": 0.375,
  "online_to_store_ratio": 0.7273,
  "churn_probability": 0.9776789,
  "top_categories": [
    "Apparel",
    "Grocery"
  ],
  "category_source": "Lab 2 processed transactions on or before 2026-04-01, ranked by purchase count"
}
```

Generated offer:

Explore our Apparel category. If your account confirms Gold status, you can earn 1.5 points per $1 of qualifying merchandise spend. Browse the selection and check your account before purchasing.

Retrieved chunk IDs: POL-LOY-011-s09-c01, POL-LOY-011-s06-c01, POL-LOY-011-s02-c01, POL-LOY-011-s10-c01, POL-RET-004-s11-c01, POL-RET-004-s06-c01, POL-SHP-007-s07-c01, POL-LOY-011-s11-c01

Safe copy fallback used: True. The policy incentive is rendered from retrieved evidence.

## Successful example 4: CUST-10002887

Profile:
```json
{
  "customer_id": "CUST-10002887",
  "loyalty_tier": "Platinum",
  "days_since_last_purchase": 183.0,
  "total_lifetime_value": 7397.69,
  "avg_order_value": 435.1582,
  "category_diversity_score": 0.5,
  "online_to_store_ratio": 0.6471,
  "churn_probability": 0.9624804,
  "top_categories": [
    "Beauty",
    "Home"
  ],
  "category_source": "Lab 2 processed transactions on or before 2026-04-01, ranked by purchase count"
}
```

Generated offer:

Explore our Beauty and Home collections to discover items that match your style. If your account confirms Platinum status and an unused annual gear credit, check whether its $100 credit applies to your gear purchase before December 31. Browse your account to see what's waiting for you and check your rewards balance.

Retrieved chunk IDs: POL-LOY-011-s09-c01, POL-LOY-011-s06-c01, POL-LOY-011-s10-c01, POL-SHP-007-s02-c01, POL-RET-004-s11-c01, POL-RET-004-s06-c01, POL-SHP-007-s07-c01, POL-LOY-011-s11-c01

Safe copy fallback used: False. The policy incentive is rendered from retrieved evidence.

## Successful example 5: CUST-10004217

Profile:
```json
{
  "customer_id": "CUST-10004217",
  "loyalty_tier": "Bronze",
  "days_since_last_purchase": 338.0,
  "total_lifetime_value": 110.56,
  "avg_order_value": 110.56,
  "category_diversity_score": 0.125,
  "online_to_store_ratio": 0.0,
  "churn_probability": 0.98665756,
  "top_categories": [
    "Apparel"
  ],
  "category_source": "Lab 2 processed transactions on or before 2026-04-01, ranked by purchase count"
}
```

Generated offer:

Explore our full range of apparel and gear to discover styles that match your preferences. If your account confirms Bronze status, you can earn 1 point per $1 of qualifying merchandise spend. Browse your account to see what's waiting for you and check your rewards balance.

Retrieved chunk IDs: POL-LOY-011-s09-c01, POL-LOY-011-s06-c01, POL-LOY-011-s02-c01, POL-SHP-007-s02-c01, POL-RET-004-s11-c01, POL-RET-004-s06-c01, POL-SHP-007-s07-c01, POL-LOY-011-s11-c01

Safe copy fallback used: False. The policy incentive is rendered from retrieved evidence.

## Observed failure: Points expiration hallucination

Profile:
```json
{
  "churn_probability": 0.74,
  "loyalty_tier": "Bronze",
  "days_since_last_purchase": 68,
  "total_lifetime_value": 312.8,
  "avg_order_value": 41.15,
  "category_diversity_score": 0.125,
  "online_to_store_ratio": 0.2,
  "top_categories": [
    "Apparel"
  ],
  "customer_id": "CUST-10000904"
}
```

Original generated offer:

We've noticed it's been a while since your last visit, and we'd love to welcome you back to NorthStar Retail. As a Bronze member, you'll earn 1 point per dollar spent on your next apparel purchase—points that never expire and can be redeemed toward future orders. Stop by your nearest store or browse our apparel selection online to see what's new.

Retrieved chunk IDs: POL-RET-004-s11-c01, POL-RET-004-s06-c01, POL-SHP-007-s07-c01, POL-LOY-011-s11-c01, KB-FAQ-022-s01-c01, POL-LOY-011-s12-c01

Why it fails: The offer says points never expire. POL-LOY-011 section 3.1 says they expire 18 months after the most recent qualifying purchase. Constraint retrieval did not return that section; the free-form model filled the gap incorrectly.

Fix: Restrict benefit claims to parsed retrieved policy, and omit expiration promises when its rule is absent. Implemented in the final renderer; never inventing an expiry term is preferable to guessing.

## Observed failure: Lifetime spend incorrectly treated as an imminent tier upgrade

Profile:
```json
{
  "churn_probability": 0.7,
  "loyalty_tier": "Silver",
  "total_lifetime_value": 1985.0,
  "days_since_last_purchase": 52,
  "avg_order_value": 132.3,
  "category_diversity_score": 0.375,
  "online_to_store_ratio": 0.61,
  "top_categories": [
    "Home",
    "Beauty"
  ],
  "customer_id": "CUST-10000588"
}
```

Original generated offer:

We'd love to have you back—as a Silver member, you earn 1.25 points per dollar on every purchase, and you're just $15 away from unlocking Gold benefits like free shipping on any order. Browse our Home and Beauty categories and check your account status to see how close you are to your next tier.

Retrieved chunk IDs: POL-LOY-011-s09-c01, POL-LOY-011-s06-c01, POL-LOY-011-s02-c01, POL-SHP-007-s02-c01, POL-RET-004-s11-c01, POL-RET-004-s06-c01, POL-SHP-007-s07-c01, POL-LOY-011-s11-c01

Why it fails: The offer claims the member is just $15 from Gold, using $1,985 lifetime value. Policy uses trailing 12-month qualifying spend. The policy threshold was retrieved, but the model applied it to the wrong definition.

Fix: Resolve tier from the system of record in production. Until that integration exists, keep Silver benefits conditional and never compute a tier-upgrade gap from lifetime value. The final renderer follows that constraint.
