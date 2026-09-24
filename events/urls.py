"""
Events & Discovery URL Configuration
====================================

Base Prefix: /api/events/

Endpoints Summary:
------------------
1. Public Discovery:
   GET    /                                            -> List active/upcoming published events with filters & pagination (public)
   GET    /featured/                                   -> Retrieve spotlight/hero banner featured event (public)
   GET    /<int:pk>/                                   -> Retrieve full event details, tiers, and host info (public)
   GET    /<int:event_id>/seating/                     -> Retrieve seating layout, section maps, & seat reservation availability (public)

2. Social Interactions:
   POST   /<int:event_id>/like/                        -> Toggle like/unlike on an event (auth)
   GET    /<int:event_id>/comments/                    -> List threaded comments and nested replies (public/auth)
   POST   /<int:event_id>/comments/                    -> Post a new comment or reply (auth)
   DELETE /<int:event_id>/comments/<int:comment_id>/   -> Delete a comment or reply (author/organizer)
   POST   /<int:event_id>/comments/<int:comment_id>/like/ -> Toggle like/unlike on a comment (auth)

3. Organizer / Manager Operations:
   GET    /manager/                                    -> List all events created by logged-in organizer (manager)
   POST   /manager/                                    -> Create a new event stage with ticket tiers & seating config (manager)
   GET    /manager/<int:pk>/                           -> Get manager view of event details & analytics (manager)
   PATCH  /manager/<int:pk>/                           -> Update event details, dates, venue, banner, or tiers (manager)
   DELETE /manager/<int:pk>/                           -> Delete an event stage (manager)
   GET    /manager/<int:event_id>/seating/             -> Retrieve manager seat layout builder data (manager)
   PUT    /manager/<int:event_id>/seating/             -> Save/update seat map layout, sections, rows & pricing (manager)
   GET    /manager/<int:event_id>/staff/               -> List assigned event gate staff members (manager)
   POST   /manager/<int:event_id>/staff/               -> Assign a user to the event staff team (manager)
   PATCH  /manager/<int:event_id>/staff/<int:staff_id>/ -> Update assigned staff permissions (manager)
   DELETE /manager/<int:event_id>/staff/<int:staff_id>/ -> Remove staff member from event (manager)
   GET    /manager/staff/users/search/                 -> Search registered users by email/name to invite as staff (manager)

4. Staff Assignment Portal:
   GET    /staff/                                      -> List active events assigned to logged-in user as gate staff (staff)

5. Saved / Bookmarked Events:
   GET    /saved/                                      -> List all events bookmarked by the current user (auth)
   POST   /saved/<int:event_id>/toggle/                -> Toggle save/bookmark status for an event (auth)
   POST   /<int:event_id>/bookmark/                    -> Alias endpoint for toggling bookmark status (auth)
   POST   /saved/clear/                                -> Clear all bookmarked events for current user (auth)
"""

from django.urls import path
from .views import (
    PublicEventListView,
    FeaturedHeroEventView,
    EventDetailView,
    ManagerEventListCreateView,
    ManagerEventDetailView,
    UserSavedEventsView,
    ToggleBookmarkView,
    ClearBookmarksView,
    ManagerEventStaffListView,
    ManagerEventStaffDetailView,
    ManagerEventStaffBulkAssignView,
    ManagerUserSearchView,
    ManagerStaffOverviewView,
    StaffAssignedEventsListView,
    ManagerEventSeatingView,
    PublicEventSeatingView,
    EventLikeToggleView,
    EventCommentListCreateView,
    EventCommentDetailView,
    CommentLikeToggleView,
    ImageUploadView,
)

urlpatterns = [
    # Universal Image Upload Endpoint (Cloudinary CDN)
    path('upload/image/', ImageUploadView.as_view(), name='event_image_upload'),

    # -------------------------------------------------------------------------
    # 1. Public Event Discovery & Details (Public)
    # -------------------------------------------------------------------------
    # GET: Lists active published events. Supports query params: ?category=, ?city=, ?search=, ?sort=, ?page=, ?page_size=
    path('', PublicEventListView.as_view(), name='event_list'),

    # GET: Returns the primary featured/hero event curated for top-level landing page banner
    path('featured/', FeaturedHeroEventView.as_view(), name='event_featured'),

    # GET: Returns comprehensive event details, ticket tier pricing, schedule, venue, organizer profile & engagement stats
    path('<int:pk>/', EventDetailView.as_view(), name='event_detail'),

    # GET: Returns seat map configuration (sections, rows, seats) and real-time booked/available status for checkout selection
    path('<int:event_id>/seating/', PublicEventSeatingView.as_view(), name='event_seating'),

    # -------------------------------------------------------------------------
    # 2. Social Interactions: Likes, Threaded Comments & Replies (Auth)
    # -------------------------------------------------------------------------
    # POST: Toggles like/unlike for the specified event for the logged-in user
    path('<int:event_id>/like/', EventLikeToggleView.as_view(), name='event_like_toggle'),

    # GET: Fetches hierarchical comment tree (comments & replies) with author metadata & like counts
    # POST: Posts a new top-level comment or reply to an existing comment (via parent_id)
    path('<int:event_id>/comments/', EventCommentListCreateView.as_view(), name='event_comment_list_create'),

    # DELETE: Removes a comment or reply (allowed by comment author or event organizer)
    path('<int:event_id>/comments/<int:comment_id>/', EventCommentDetailView.as_view(), name='event_comment_detail'),

    # POST: Toggles like/unlike on a specific comment for the logged-in user
    path('<int:event_id>/comments/<int:comment_id>/like/', CommentLikeToggleView.as_view(), name='comment_like_toggle'),

    # -------------------------------------------------------------------------
    # 3. Manager / Organizer Operations (Organizer Only - IsManagerUser)
    # -------------------------------------------------------------------------
    # GET: Returns all events organized by the current user (published, draft, ended) with sales summaries
    # POST: Creates a new event stage along with its ticket tiers and seating configuration
    path('manager/', ManagerEventListCreateView.as_view(), name='manager_events'),

    # GET: Retrieves detailed manager view of a specific event
    # PUT/PATCH: Updates event metadata, dates, venue, media banners, and ticket tiers
    # DELETE: Deletes the event stage and associated records
    path('manager/<int:pk>/', ManagerEventDetailView.as_view(), name='manager_event_detail'),

    # GET: Retrieves seating layout builder data for the event
    # PUT: Creates/updates custom interactive visual seating layout, sections, rows, seats, and tier associations
    path('manager/<int:event_id>/seating/', ManagerEventSeatingView.as_view(), name='manager_event_seating'),

    # GET: Lists all staff members assigned to work check-in / gate scanning for this event
    # POST: Assigns a user to the event staff team with custom permissions (e.g. can_scan, can_view_sales)
    path('manager/<int:event_id>/staff/', ManagerEventStaffListView.as_view(), name='manager_event_staff_list'),

    # PATCH: Updates permissions for an assigned staff member
    # DELETE: Unassigns / removes staff member from the event
    path('manager/<int:event_id>/staff/<int:staff_id>/', ManagerEventStaffDetailView.as_view(), name='manager_event_staff_detail'),

    # POST: Bulk assigns studio staff members to the event in one call
    path('manager/<int:event_id>/staff/bulk-assign/', ManagerEventStaffBulkAssignView.as_view(), name='manager_event_staff_bulk_assign'),

    # GET: Searches registered platform users by email or name to add as event staff (?q=<query>)
    path('manager/staff/users/search/', ManagerUserSearchView.as_view(), name='manager_staff_user_search'),

    # GET: Returns aggregated team / staff roster across all events hosted by the manager
    path('manager/staff-overview/', ManagerStaffOverviewView.as_view(), name='manager_staff_overview'),

    # -------------------------------------------------------------------------
    # 4. Staff Portal (Staff / Authenticated Users)
    # -------------------------------------------------------------------------
    # GET: Returns all active/upcoming events where current logged-in user is an assigned staff scanner
    path('staff/', StaffAssignedEventsListView.as_view(), name='staff_assigned_events'),

    # -------------------------------------------------------------------------
    # 5. User Bookmarks / Saved Events (Authenticated)
    # -------------------------------------------------------------------------
    # GET: Returns list of all events bookmarked / saved by current user
    path('saved/', UserSavedEventsView.as_view(), name='user_saved_events'),

    # POST: Toggles bookmark status (saves if not saved, unsaves if already saved)
    path('saved/<int:event_id>/toggle/', ToggleBookmarkView.as_view(), name='toggle_bookmark'),

    # POST: Alias endpoint for toggling bookmark status
    path('<int:event_id>/bookmark/', ToggleBookmarkView.as_view(), name='event_bookmark_alias'),

    # POST: Clears / removes all bookmarks for the authenticated user
    path('saved/clear/', ClearBookmarksView.as_view(), name='clear_bookmarks'),
]


