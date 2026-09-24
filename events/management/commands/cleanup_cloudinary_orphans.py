import os
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime
import cloudinary
import cloudinary.api
from events.models import Event
from accounts.models import OrganizerProfile
from events.utils.media_utils import extract_cloudinary_public_id


class Command(BaseCommand):
    help = "Scans Cloudinary for unlinked/abandoned (orphan) images and safely purges them."

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Age threshold in hours (default: 24). Images uploaded less than N hours ago are kept in grace period.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate scan and list orphan images without deleting anything from Cloudinary.'
        )
        parser.add_argument(
            '--prefix',
            type=str,
            default='evento/',
            help='Cloudinary folder prefix to scan (default: "evento/").'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Maximum number of assets to delete in a single Cloudinary API call (default: 100).'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Execute deletions immediately without interactive confirmation.'
        )

    def handle(self, *args, **options):
        hours_threshold = options['hours']
        dry_run = options['dry_run']
        prefix = options['prefix']
        batch_size = options['batch_size']
        force = options['force']

        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))
        self.stdout.write(self.style.MIGRATE_HEADING("  EVENTO CLOUDINARY ORPHAN CLEANUP & STORAGE REAPER"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))
        self.stdout.write(f"• Prefix:         {prefix}")
        self.stdout.write(f"• Grace Period:   {hours_threshold} hours")
        self.stdout.write(f"• Mode:           {'SIMULATION (DRY RUN)' if dry_run else 'LIVE PURGE'}\n")

        # 1. Verify Cloudinary configuration
        cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
        api_key = os.environ.get('CLOUDINARY_API_KEY')
        api_secret = os.environ.get('CLOUDINARY_API_SECRET')

        if not (cloud_name and api_key and api_secret):
            self.stdout.write(
                self.style.ERROR(
                    "❌ Cloudinary credentials not configured in environment variables. Aborting."
                )
            )
            return

        # 2. Collect all active public_ids from database
        self.stdout.write("🔍 Collecting active image references from database...")
        active_public_ids = set()

        # From Events
        for banner in Event.objects.exclude(banner_image='').exclude(banner_image__isnull=True).values_list('banner_image', flat=True):
            pid = extract_cloudinary_public_id(banner)
            if pid:
                active_public_ids.add(pid)

        # From Organizer Profiles
        for logo in OrganizerProfile.objects.exclude(logo_url='').exclude(logo_url__isnull=True).values_list('logo_url', flat=True):
            pid = extract_cloudinary_public_id(logo)
            if pid:
                active_public_ids.add(pid)

        self.stdout.write(
            self.style.SUCCESS(
                f"   Found {len(active_public_ids)} active image references across Events & Profiles in DB."
            )
        )

        # 3. Fetch assets from Cloudinary with pagination
        self.stdout.write(f"☁️  Querying Cloudinary API for assets under '{prefix}'...")
        all_assets = []
        next_cursor = None

        try:
            while True:
                params = {
                    'type': 'upload',
                    'prefix': prefix,
                    'max_results': 500,
                }
                if next_cursor:
                    params['next_cursor'] = next_cursor

                res = cloudinary.api.resources(**params)
                resources = res.get('resources', [])
                all_assets.extend(resources)

                next_cursor = res.get('next_cursor')
                if not next_cursor:
                    break
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to query Cloudinary Admin API: {e}"))
            return

        self.stdout.write(f"   Fetched {len(all_assets)} total assets from Cloudinary.\n")

        if not all_assets:
            self.stdout.write(self.style.SUCCESS("✨ Cloudinary is completely clean. No assets found."))
            return

        # 4. Classify assets
        now = timezone.now()
        threshold_delta = datetime.timedelta(hours=hours_threshold)
        cutoff_dt = now - threshold_delta

        active_count = 0
        recent_unlinked = []
        orphans_to_delete = []
        total_orphan_bytes = 0

        for asset in all_assets:
            public_id = asset.get('public_id')
            created_at_raw = asset.get('created_at')
            asset_bytes = asset.get('bytes', 0)
            asset_format = asset.get('format', 'unknown')

            # Parse created_at datetime
            created_dt = parse_datetime(created_at_raw) if created_at_raw else None
            if created_dt and timezone.is_naive(created_dt):
                created_dt = timezone.make_aware(created_dt, timezone.utc)

            # Check if active in DB
            if public_id in active_public_ids:
                active_count += 1
                continue

            # Check if within grace period
            if created_dt and created_dt > cutoff_dt:
                age_minutes = int((now - created_dt).total_seconds() / 60)
                recent_unlinked.append({
                    'public_id': public_id,
                    'bytes': asset_bytes,
                    'age': f"{age_minutes}m ago",
                    'format': asset_format
                })
            else:
                age_hours = int((now - created_dt).total_seconds() / 3600) if created_dt else 'unknown'
                orphans_to_delete.append({
                    'public_id': public_id,
                    'bytes': asset_bytes,
                    'age': f"{age_hours}h ago" if isinstance(age_hours, (int, float)) else str(age_hours),
                    'format': asset_format
                })
                total_orphan_bytes += asset_bytes

        # 5. Display classification findings
        self.stdout.write(self.style.MIGRATE_LABEL("📊 Scan Classification Summary:"))
        self.stdout.write(f"   • Active in Database:     {active_count} assets")
        self.stdout.write(f"   • In Grace Period (<{hours_threshold}h): {len(recent_unlinked)} assets (protected from deletion)")
        self.stdout.write(f"   • Confirmed Orphans:      {len(orphans_to_delete)} assets ({total_orphan_bytes / (1024*1024):.2f} MB)")

        if recent_unlinked:
            self.stdout.write("\n⏳ Protected Assets in Grace Period (upload in progress / recent):")
            for r in recent_unlinked[:10]:
                self.stdout.write(f"   - {r['public_id']} ({r['format']}, {r['bytes']/1024:.1f} KB, uploaded {r['age']})")
            if len(recent_unlinked) > 10:
                self.stdout.write(f"   ... and {len(recent_unlinked) - 10} more.")

        if not orphans_to_delete:
            self.stdout.write(self.style.SUCCESS("\n🎉 Clean! No orphaned assets eligible for deletion."))
            return

        self.stdout.write("\n🗑️  Orphaned Assets Targeted for Removal:")
        for o in orphans_to_delete[:20]:
            self.stdout.write(f"   - {o['public_id']} ({o['format']}, {o['bytes']/1024:.1f} KB, uploaded {o['age']})")
        if len(orphans_to_delete) > 20:
            self.stdout.write(f"   ... and {len(orphans_to_delete) - 20} more.")

        # 6. Execute Deletion or Dry Run
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[DRY RUN] Simulation complete. {len(orphans_to_delete)} assets ({total_orphan_bytes / (1024*1024):.2f} MB) would be permanently deleted."
                )
            )
            return

        if not force:
            confirm = input(
                f"\n⚠️  Permanently delete {len(orphans_to_delete)} orphaned images from Cloudinary? [y/N]: "
            )
            if confirm.lower() not in ['y', 'yes']:
                self.stdout.write(self.style.NOTICE("Action cancelled by user."))
                return

        self.stdout.write(f"\n🚀 Deleting {len(orphans_to_delete)} orphaned assets in batches of {batch_size}...")
        orphan_pids = [o['public_id'] for o in orphans_to_delete]
        deleted_count = 0
        error_count = 0

        for i in range(0, len(orphan_pids), batch_size):
            batch = orphan_pids[i:i + batch_size]
            try:
                del_res = cloudinary.api.delete_resources(batch)
                deleted_dict = del_res.get('deleted', {})
                for pid, status in deleted_dict.items():
                    if status in ['deleted', 'not_found']:
                        deleted_count += 1
                    else:
                        error_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error deleting batch: {e}"))
                error_count += len(batch)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Cleanup Complete! Successfully deleted {deleted_count} orphaned images ({total_orphan_bytes / (1024*1024):.2f} MB recovered)."
            )
        )
        if error_count > 0:
            self.stdout.write(self.style.WARNING(f"⚠️  {error_count} assets could not be deleted."))
