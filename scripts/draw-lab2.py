"""Render reproducible Lab 2 diagrams using matplotlib."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "docs"
NAVY, BLUE, TEAL = "#14283f", "#e9f1fc", "#e6f5f1"


def canvas(title, subtitle):
    fig, ax = plt.subplots(figsize=(18, 11))
    fig.patch.set_facecolor("#f8fafc")
    ax.set(xlim=(0, 18), ylim=(0, 11))
    ax.axis("off")
    ax.text(.35, 10.5, title, fontsize=24, fontweight="bold", color=NAVY)
    ax.text(.35, 10.05, subtitle, fontsize=12, color="#53657c")
    return fig, ax


def box(ax, x, y, text, w=3.5, h=1.1, color=BLUE):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06,rounding_size=.12",
                               facecolor=color, edgecolor="#9db2ca", linewidth=1.2))
    ax.text(x+w/2, y+h/2, text, ha="center", va="center", fontsize=11, color=NAVY)


def arrow(ax, start, end, label="", offset=(0, .18)):
    ax.annotate("", xy=end, xytext=start,
                arrowprops=dict(arrowstyle="-|>", color="#456580", lw=1.6))
    if label:
        x, y = (start[0]+end[0])/2+offset[0], (start[1]+end[1])/2+offset[1]
        ax.text(x, y, label, ha="center", va="center", fontsize=9, color=NAVY,
                bbox=dict(facecolor="#f8fafc", edgecolor="none", pad=2))


fig, ax = canvas("NorthStar | Customer data lineage", "Lab 2 - transaction-level cleaning, customer-level features, separate future outcome labels")
box(ax, .4, 8.25, "Source system\nSynthetic transaction CSV")
box(ax, 7.1, 8.25, "S3 raw/customers/\nCSV transactions")
arrow(ax, (4, 8.8), (7, 8.8), "CSV upload\nLab operator (AWS CLI)")
box(ax, 13.8, 8.25, "Glue Crawler\nraw-crawler")
arrow(ax, (10.7, 8.8), (13.7, 8.8), "CSV schema scan\nDataEngineer")
box(ax, 13.8, 5.8, "Glue Data Catalog\nnorthstar_dev.customers")
arrow(ax, (15.55, 8.15), (15.55, 7), "Table metadata\nDataEngineer", offset=(0, 0))
box(ax, 7.1, 5.8, "Glue Transform Job\nNormalize, impute, deduplicate")
arrow(ax, (13.7, 6.35), (10.7, 6.35), "Catalog schema + S3 CSV\nDataEngineer reads")
box(ax, .4, 5.8, "S3 processed/customers/\nParquet: one row / transaction")
arrow(ax, (7, 6.35), (4, 6.35), "Parquet write\nDataEngineer")
box(ax, .4, 3.1, "Glue Feature Engineer Job\nAggregate + label customers", color=TEAL)
arrow(ax, (2.15, 5.7), (2.15, 4.3), "Parquet read\nDataEngineer", offset=(0, 0))
box(ax, 7.1, 3.1, "S3 features/customers/\nParquet: one row / customer", color=TEAL)
arrow(ax, (4, 3.65), (7, 3.65), "Parquet write\nDataEngineer")
box(ax, .4, .45, "SageMaker Feature Store\ncustomer-features (16 fields)", color=TEAL)
arrow(ax, (2.15, 3), (2.15, 1.65), "PutRecord (feature records)\nDataEngineer", offset=(0, 0))
box(ax, 7.1, .45, "Online store\nReal-time feature records", color=TEAL)
arrow(ax, (4, 1), (7, 1), "Feature records\nFeature Store service")
box(ax, 13.8, .45, "S3 features/offline-store/\nService-managed Parquet", color=TEAL)
ax.plot([3.9, 5, 5, 15.55], [.65, .65, .1, .1], color="#456580", lw=1.2)
arrow(ax, (15.55, .1), (15.55, .4))
ax.text(11.4, -.18, "Offline Parquet writes: Feature Store assuming DataEngineer", fontsize=9, ha="center", color=NAVY)
ax.text(13.9, 4.6, "OBSERVATION\nPurchases through Apr 1, 2026\n13 features from past behavior\n\nOUTCOME\nApr 2 - Jun 30, 2026\nNo purchases = churn_label 1\n\nLab 3 consumer: MLEngineer",
        fontsize=11, color=NAVY, va="top", linespacing=1.5)
fig.savefig(OUT / "lab2-data-lineage.png", dpi=160, bbox_inches="tight")
plt.close(fig)

fig, ax = canvas("NorthStar | Platform architecture", "us-east-1 - VPC 10.0.0.0/16 - Availability Zone us-east-1a")
box(ax, .5, 1.4, "", w=11, h=7.8, color="#eef3f9")
ax.text(.8, 8.7, "northstar-dev-vpc", fontsize=15, color=NAVY)
box(ax, 1, 5.1, "PUBLIC SUBNET 10.0.100.0/24\nNAT Gateway + Elastic IP\nPublic route: 0.0.0.0/0 -> IGW", w=5, h=2)
box(ax, 1, 2.2, "PRIVATE SUBNET 10.0.1.0/24\nSageMaker Studio (VpcOnly)\nGlue Spark workers + NETWORK connection\nPrivate route: 0.0.0.0/0 -> NAT", w=9.5, h=2)
box(ax, 7, 5.1, "Internet Gateway\nOutbound AWS API / ECR access", w=3.5, h=2)
arrow(ax, (3.5, 4.3), (3.5, 5), "Outbound")
arrow(ax, (6.1, 6.1), (6.9, 6.1))
box(ax, 12.6, 7.2, "S3 data bucket\nPrivate, versioned, SSE-S3\nFive retention rules", w=4.5, h=1.7)
box(ax, 12.6, 4.6, "Regional data services\nGlue Catalog + Crawler\nFeature Store online + offline", w=4.5, h=1.7)
box(ax, 12.6, 1.4, "IAM access boundaries\nDataEngineer: data pipeline writes\nMLEngineer: training / artifacts\nModelMonitor: observe + metrics\nGlue security group: self ingress", w=4.5, h=2.4)
arrow(ax, (10.6, 6.1), (12.5, 8), "HTTPS")
ax.text(.6, .55, "LocalStack: VPC, storage and all three roles; NAT and lifecycle disabled. SageMaker / Glue run in real AWS.", fontsize=12, color=NAVY)
fig.savefig(OUT / "lab2-architecture.png", dpi=160, bbox_inches="tight")
plt.close(fig)
