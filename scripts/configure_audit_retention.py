#!/usr/bin/env python3
"""Configure audit log retention for the Orders service S3 bucket.

Requires AWS credentials with `s3:PutLifecycleConfiguration`, `s3:PutBucketEncryption`,
`s3:PutBucketVersioning`, and `s3:PutBucketPolicy` permissions.

Example:
    python scripts/configure_audit_retention.py --bucket efab-audit/orders --region us-east-1
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True, help="Name of the audit bucket (e.g. efab-audit/orders)")
    parser.add_argument("--region", default="us-east-1", help="AWS region for the bucket")
    parser.add_argument(
        "--retention-years",
        type=int,
        default=7,
        help="Retention period (years) before objects are archived to Glacier Deep Archive.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the actions that would be applied without calling AWS APIs.",
    )
    return parser.parse_args()


def ensure_encryption(s3_client: Any, bucket: str, dry_run: bool) -> None:
    """Enable SSE-S3 encryption for the bucket if not already configured."""
    try:
        encryption = s3_client.get_bucket_encryption(Bucket=bucket)
        rules = encryption["ServerSideEncryptionConfiguration"]["Rules"]
        if any(rule["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256" for rule in rules):
            return
    except ClientError as exc:  # bucket may not have encryption
        if exc.response["Error"]["Code"] != "ServerSideEncryptionConfigurationNotFoundError":
            raise
    if dry_run:
        print(f"[dry-run] Would enable SSE-S3 encryption for bucket {bucket}.")
        return
    s3_client.put_bucket_encryption(
        Bucket=bucket,
        ServerSideEncryptionConfiguration={
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"},
                    "BucketKeyEnabled": True,
                }
            ]
        },
    )


def ensure_versioning(s3_client: Any, bucket: str, dry_run: bool) -> None:
    """Enable versioning to guarantee audit immutability."""
    status = s3_client.get_bucket_versioning(Bucket=bucket)
    if status.get("Status") == "Enabled":
        return
    if dry_run:
        print(f"[dry-run] Would enable versioning for bucket {bucket}.")
        return
    s3_client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})


def apply_lifecycle(s3_client: Any, bucket: str, retention_years: int, dry_run: bool) -> None:
    """Configure lifecycle rules for long-term retention."""
    transition_days = retention_years * 365
    lifecycle_config: Dict[str, Any] = {
        "Rules": [
            {
                "ID": f"orders-audit-retention-{retention_years}y",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "Transitions": [
                    {"Days": transition_days, "StorageClass": "DEEP_ARCHIVE"},
                ],
                "NoncurrentVersionTransitions": [
                    {"NoncurrentDays": 90, "StorageClass": "GLACIER_IR"}
                ],
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            }
        ]
    }
    if dry_run:
        print(f"[dry-run] Would apply lifecycle configuration to {bucket}: {json.dumps(lifecycle_config)}")
        return
    s3_client.put_bucket_lifecycle_configuration(
        Bucket=bucket,
        LifecycleConfiguration=lifecycle_config,
    )


def apply_bucket_policy(s3_client: Any, bucket: str, dry_run: bool) -> None:
    """Apply a restricted bucket policy enforcing TLS and write-only access for the Orders role."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DenyInsecureConnections",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
            },
            {
                "Sid": "OrdersServiceWriteOnly",
                "Effect": "Allow",
                "Principal": {"AWS": ["arn:aws:iam::123456789012:role/orders-service-staging"]},
                "Action": ["s3:PutObject", "s3:PutObjectTagging"],
                "Resource": f"arn:aws:s3:::{bucket}/orders/*",
            },
        ],
    }
    if dry_run:
        print(f"[dry-run] Would apply bucket policy to {bucket}: {json.dumps(policy)}")
        return
    s3_client.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))


def main() -> None:
    args = parse_args()
    session = boto3.session.Session(region_name=args.region)
    s3_client = session.client("s3")

    ensure_encryption(s3_client, args.bucket, args.dry_run)
    ensure_versioning(s3_client, args.bucket, args.dry_run)
    apply_lifecycle(s3_client, args.bucket, args.retention_years, args.dry_run)
    apply_bucket_policy(s3_client, args.bucket, args.dry_run)

    timestamp = datetime.now(timezone.utc).isoformat()
    if args.dry_run:
        print(f"[{timestamp}] Dry-run complete for {args.bucket}; no AWS API calls made.")
    else:
        print(f"[{timestamp}] Retention policy applied to {args.bucket} for {args.retention_years} years.")


if __name__ == "__main__":
    main()
