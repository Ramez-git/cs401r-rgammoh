"""Attach the actual training inputs and evaluation to this run's package."""
import argparse
import json
from pathlib import Path

import boto3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execution-arn", required=True)
    parser.add_argument("--package-arn", required=True)
    parser.add_argument("--metrics", required=True)
    args = parser.parse_args()
    sm = boto3.client("sagemaker")
    steps = sm.list_pipeline_execution_steps(PipelineExecutionArn=args.execution_arn)["PipelineExecutionSteps"]
    job_arn = next(s["Metadata"]["TrainingJob"]["Arn"] for s in steps if s["StepName"] == "TrainChurnModel")
    job = sm.describe_training_job(TrainingJobName=job_arn.rsplit("/", 1)[1])
    metrics = json.loads(Path(args.metrics).read_text())
    numeric = ["auc_roc", "baseline_auc", "precision_top10", "recall_top10",
               "lift_ci_low", "lift_ci_high", "fairness_recall_gap"]
    metadata = {key: str(metrics[key]) for key in numeric}
    metadata.update(
        code_commit_sha=job["Environment"]["COMMIT_SHA"],
        training_data_s3_uri=job["InputDataConfig"][0]["DataSource"]["S3DataSource"]["S3Uri"],
        training_data_event_time=str(metrics["data_event_time"]),
        training_job_arn=job_arn,
        training_started_at=job["TrainingStartTime"].isoformat(),
        metrics_s3_uri=job["Environment"]["METRICS_S3_URI"],
    )
    sm.update_model_package(ModelPackageArn=args.package_arn, CustomerMetadataProperties=metadata)
    print("Stored model lineage: " + json.dumps(metadata, sort_keys=True))


if __name__ == "__main__":
    main()
