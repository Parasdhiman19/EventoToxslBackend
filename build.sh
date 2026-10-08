#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Collecting static assets..."
python manage.py collectstatic --no-input

echo "==> Running database migrations..."
python manage.py migrate --no-input

echo "==> Ensuring Super Admin exists..."
python manage.py shell -c "
from accounts.models import User
for email in ['admin@evento.com', 'superadmin@evento.com']:
    u, _ = User.objects.get_or_create(email=email)
    u.full_name = 'Super Administrator'
    u.role = 'admin'
    u.is_staff = True
    u.is_superuser = True
    u.is_active = True
    u.set_password('AdminEvento2026!')
    u.save()
print('==> Super Admin verified!')
"

echo "==> Seeding rich platform demo data (100 events, organizers, attendees, seat maps)..."
python manage.py seed_100_events

echo "==> Build completed successfully!"

