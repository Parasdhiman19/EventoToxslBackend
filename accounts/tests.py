from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User, OrganizerProfile, SettlementAccount
from accounts.constants import USER, MANAGER


class AccountsAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='testuser@evento.com',
            password='Password123!',
            full_name='Test User',
            role=USER
        )
        self.manager = User.objects.create_user(
            email='testmanager@evento.com',
            password='Password123!',
            full_name='Test Manager',
            role=MANAGER
        )
        self.org_profile = OrganizerProfile.objects.create(
            user=self.manager,
            organization_name='Test Studio',
        )

    def test_signup_customer(self):
        response = self.client.post('/api/auth/signup/', {
            'fullName': 'Alice Wonderland',
            'email': 'alice@example.com',
            'password': 'Password123!',
            'role': 'user'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['email'], 'alice@example.com')
        self.assertEqual(response.data['user']['role'], 'user')
        self.assertIn('refresh_token', response.cookies)

    def test_signup_organizer(self):
        response = self.client.post('/api/auth/signup/', {
            'fullName': 'Bob Producer',
            'email': 'bob@example.com',
            'password': 'Password123!',
            'role': 'manager'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['role'], 'manager')
        self.assertTrue(response.data['user']['isOrganizer'])
        # Ensure OrganizerProfile was created
        user = User.objects.get(email='bob@example.com')
        self.assertTrue(hasattr(user, 'organizer_profile'))

    def test_login_success(self):
        response = self.client.post('/api/auth/login/', {
            'email': 'testuser@evento.com',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh_token', response.cookies)

    def test_login_invalid_password(self):
        response = self.client.post('/api/auth/login/', {
            'email': 'testuser@evento.com',
            'password': 'WrongPassword'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_refresh(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'testuser@evento.com',
            'password': 'Password123!'
        })
        refresh_token = login_res.cookies['refresh_token'].value

        # Client with refresh cookie
        self.client.cookies['refresh_token'] = refresh_token
        refresh_res = self.client.post('/api/auth/token/refresh/')
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        self.assertIn('access', refresh_res.data)

    def test_me_authenticated(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'testuser@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        me_res = self.client.get('/api/auth/me/')
        self.assertEqual(me_res.status_code, status.HTTP_200_OK)
        self.assertEqual(me_res.data['email'], 'testuser@evento.com')

    def test_become_organizer(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'testuser@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        res = self.client.post('/api/auth/become-organizer/', {
            'organizationName': 'My New Stage',
            'bio': 'Music and live art curators'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['user']['isOrganizer'])

    def test_organizer_settings_and_settlement(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'testmanager@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Get settings
        settings_res = self.client.get('/api/auth/settings/')
        self.assertEqual(settings_res.status_code, status.HTTP_200_OK)

        # Patch settings including logoUrl
        patch_res = self.client.patch('/api/auth/settings/', {
            'organizationName': 'Updated Studio LLC',
            'instagram': '@updatedstudio',
            'logoUrl': 'https://res.cloudinary.com/demo/image/upload/studio_logo.png'
        }, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['profile']['organizationName'], 'Updated Studio LLC')
        self.assertEqual(patch_res.data['profile']['logoUrl'], 'https://res.cloudinary.com/demo/image/upload/studio_logo.png')

        # Verify persisted in database
        self.org_profile.refresh_from_db()
        self.assertEqual(self.org_profile.logo_url, 'https://res.cloudinary.com/demo/image/upload/studio_logo.png')

        # Add settlement account (PayPal)
        acc_res = self.client.post('/api/auth/settlement-accounts/', {
            'paypalEmail': 'manager.paypal@example.com',
            'isPrimary': True
        }, format='json')
        self.assertEqual(acc_res.status_code, status.HTTP_201_CREATED)

    def test_studio_staff_crud(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'testmanager@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Add staff member to studio roster
        post_res = self.client.post('/api/auth/studio-staff/', {
            'email': 'testuser@evento.com',
            'roleTitle': 'Gate Lead & Scanner',
            'defaultCanViewAttendees': True,
            'defaultCanCheckIn': True,
            'defaultCanEditAttendees': False,
            'phone': '+1 (555) 019-2831',
            'notes': 'Lead scanner for main gate VIP lane.'
        }, format='json')
        self.assertEqual(post_res.status_code, status.HTTP_201_CREATED)
        staff_id = post_res.data['id']
        self.assertEqual(post_res.data['roleTitle'], 'Gate Lead & Scanner')
        self.assertEqual(post_res.data['email'], 'testuser@evento.com')

        # 2. List studio staff members
        list_res = self.client.get('/api/auth/studio-staff/')
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]['id'], staff_id)

        # 3. Patch studio staff member
        patch_res = self.client.patch(f'/api/auth/studio-staff/{staff_id}/', {
            'roleTitle': 'Head of Stage Operations',
            'defaultCanEditAttendees': True
        }, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['roleTitle'], 'Head of Stage Operations')
        self.assertTrue(patch_res.data['defaultCanEditAttendees'])

        # 4. Delete studio staff member
        del_res = self.client.delete(f'/api/auth/studio-staff/{staff_id}/')
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)

        # 5. Verify roster empty
        list_res_2 = self.client.get('/api/auth/studio-staff/')
        self.assertEqual(len(list_res_2.data), 0)

    def test_update_user_profile(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'testuser@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        patch_res = self.client.patch('/api/auth/me/', {
            'fullName': 'Paras Dhiman',
            'username': 'paras_dhiman',
            'bio': 'Passionate event attendee & tech lover',
            'phone': '+91 98765 43210',
            'city': 'Chandigarh',
            'emailNotifications': False,
            'avatarUrl': 'https://res.cloudinary.com/demo/image/upload/avatar.jpg'
        }, format='json')

        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['user']['fullName'], 'Paras Dhiman')
        self.assertEqual(patch_res.data['user']['username'], 'paras_dhiman')
        self.assertEqual(patch_res.data['user']['bio'], 'Passionate event attendee & tech lover')
        self.assertEqual(patch_res.data['user']['phone'], '+91 98765 43210')
        self.assertEqual(patch_res.data['user']['city'], 'Chandigarh')
        self.assertFalse(patch_res.data['user']['emailNotifications'])
        self.assertEqual(patch_res.data['user']['avatarUrl'], 'https://res.cloudinary.com/demo/image/upload/avatar.jpg')

    def test_change_password_success_and_failure(self):
        login_res = self.client.post('/api/auth/login/', {
            'email': 'testuser@evento.com',
            'password': 'Password123!'
        })
        token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Invalid old password fails
        fail_res = self.client.post('/api/auth/change-password/', {
            'oldPassword': 'WrongOldPassword',
            'newPassword': 'NewSecurePassword123!'
        }, format='json')
        self.assertEqual(fail_res.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. Valid old password succeeds
        ok_res = self.client.post('/api/auth/change-password/', {
            'oldPassword': 'Password123!',
            'newPassword': 'NewSecurePassword123!'
        }, format='json')
        self.assertEqual(ok_res.status_code, status.HTTP_200_OK)

        # 3. Verify user can now log in with new password
        self.client.credentials()  # Clear credentials
        new_login = self.client.post('/api/auth/login/', {
            'email': 'testuser@evento.com',
            'password': 'NewSecurePassword123!'
        })
        self.assertEqual(new_login.status_code, status.HTTP_200_OK)



