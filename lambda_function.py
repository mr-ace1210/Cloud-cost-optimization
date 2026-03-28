import boto3
import datetime
from botocore.exceptions import ClientError, NoRegionError

# ✅ Specify region (change if needed)
REGION = "ap-south-1"

def lambda_handler(event=None, context=None):
    try:
        ec2 = boto3.client('ec2', region_name=REGION)
        s3 = boto3.client('s3', region_name=REGION)
    except NoRegionError:
        print("Region not specified. Please configure AWS region.")
        return

    print("🚀 Starting AWS Cost Optimization Cleanup...")

    # =========================
    # 🔹 EBS SNAPSHOT CLEANUP
    # =========================
    try:
        snapshots = ec2.describe_snapshots(OwnerIds=['self'])['Snapshots']

        instances = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
        )

        active_instance_ids = {
            instance['InstanceId']
            for res in instances['Reservations']
            for instance in res['Instances']
        }

        for snapshot in snapshots:
            snapshot_id = snapshot['SnapshotId']
            volume_id = snapshot.get('VolumeId')

            if not volume_id:
                ec2.delete_snapshot(SnapshotId=snapshot_id)
                print(f"🗑 Deleted snapshot {snapshot_id} (no volume)")
                continue

            try:
                volumes = ec2.describe_volumes(VolumeIds=[volume_id])['Volumes']
                attachments = volumes[0]['Attachments']

                if not attachments:
                    ec2.delete_snapshot(SnapshotId=snapshot_id)
                    print(f"🗑 Deleted snapshot {snapshot_id} (unused volume)")

            except ClientError as e:
                if e.response['Error']['Code'] == 'InvalidVolume.NotFound':
                    ec2.delete_snapshot(SnapshotId=snapshot_id)
                    print(f"🗑 Deleted snapshot {snapshot_id} (volume not found)")

    except Exception as e:
        print(f"❌ Snapshot cleanup error: {e}")

    # =========================
    # 🔹 ELASTIC IP CLEANUP
    # =========================
    try:
        addresses = ec2.describe_addresses()['Addresses']

        for address in addresses:
            allocation_id = address.get('AllocationId')
            instance_id = address.get('InstanceId')

            if not instance_id and allocation_id:
                ec2.release_address(AllocationId=allocation_id)
                print(f"🗑 Released Elastic IP {address.get('PublicIp')}")

    except Exception as e:
        print(f"❌ Elastic IP cleanup error: {e}")

    # =========================
    # 🔹 S3 CLEANUP (SAFE VERSION)
    # =========================
    try:
        buckets = s3.list_buckets()['Buckets']
        current_date = datetime.datetime.now(datetime.timezone.utc)
        threshold = current_date - datetime.timedelta(days=30)

        for bucket in buckets:
            bucket_name = bucket['Name']

            try:
                # Get last modified object
                objects = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)

                if 'Contents' not in objects:
                    print(f"⚠ Bucket {bucket_name} is empty, skipping deletion")
                    continue

                last_modified = objects['Contents'][0]['LastModified']

                if last_modified < threshold:
                    print(f"⚠ Bucket {bucket_name} inactive >30 days (not deleting for safety)")
                    # ⚠ Commented for safety
                    # s3.delete_bucket(Bucket=bucket_name)

            except ClientError as e:
                print(f"⚠ Could not check bucket {bucket_name}: {e}")

    except Exception as e:
        print(f"❌ S3 cleanup error: {e}")

    print("✅ Cleanup Completed Successfully")


# 🔹 Run locally
if __name__ == "__main__":
    lambda_handler()