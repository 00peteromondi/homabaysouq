from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from .models import Store, Subscription, MpesaPayment
from django.urls import reverse
from django.core.exceptions import ValidationError
from listings.models import Listing, Category
from listings.forms import ListingForm
from .forms import StoreForm
from listings.models import ListingImage


def store_list(request):
    stores = Store.objects.filter()
    return render(request, 'storefront/store_list.html', {'stores': stores})


def store_detail(request, slug):
    store = get_object_or_404(Store, slug=slug)
    # Only show listings associated with this specific store
    products = Listing.objects.filter(store=store, is_active=True)
    return render(request, 'storefront/store_detail.html', {'store': store, 'products': products})


def product_detail(request, store_slug, slug):
    store = get_object_or_404(Store, slug=store_slug)
    # Only show products associated with this specific store
    product = get_object_or_404(Listing, store=store, slug=slug, is_active=True)
    return render(request, 'storefront/product_detail.html', {'store': store, 'product': product})


@login_required
def seller_dashboard(request):
    stores = Store.objects.filter(owner=request.user)
    # Compute some simple metrics for the dashboard
    # Get all listings from all stores
    total_listings = sum(store.listings.count() for store in stores)
    premium_stores = stores.filter(is_premium=True).count()
    # total_views isn't tracked on listings; default to 0 for now
    total_views = 0

    # free listing limit from settings
    free_limit = getattr(settings, 'STORE_FREE_LISTING_LIMIT', 5)
    remaining = max(free_limit - total_listings, 0)

    # All listings grouped by store (for dashboard display)
    user_listings = Listing.objects.filter(store__in=stores).order_by('-date_created')

    return render(request, 'storefront/dashboard.html', {
        'stores': stores,
        'total_listings': total_listings,
        'premium_stores': premium_stores,
        'total_views': total_views,
        'free_limit': free_limit,
        'remaining_slots': remaining,
        'user_listings': user_listings,
    })


@login_required
def store_create(request):
    """
    Create a new store with enforced subscription-based limits.
    Users can only create multiple stores if they have a premium store or active subscription.
    """
    # Check existing stores and subscription status
    existing_stores = Store.objects.filter(owner=request.user)
    has_premium = existing_stores.filter(is_premium=True).exists()
    has_active_subscription = Subscription.objects.filter(store__owner=request.user, status='active').exists()

    # Enforce store limit for free users
    if existing_stores.exists() and not (has_premium or has_active_subscription):
        first_store = existing_stores.first()
        messages.warning(request, 'You must upgrade to Pro (subscribe) to create additional storefronts.')
        return redirect('storefront:store_edit', slug=first_store.slug)

    # Show store creation confirmation for users coming from listing creation
    if request.GET.get('from') == 'listing':
        return render(request, 'storefront/confirm_store_create.html')

    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            store = form.save(commit=False)
            store.owner = request.user
            
            try:
                # This will trigger the clean() method which enforces store limits
                store.full_clean()
                store.save()

                # Process logo and cover image
                if 'logo' in request.FILES:
                    store.logo = request.FILES['logo']
                if 'cover_image' in request.FILES:
                    store.cover_image = request.FILES['cover_image']
                store.save()

                messages.success(request, 'Store created successfully!')
                return redirect('storefront:seller_dashboard')
                
            except ValidationError as e:
                # Handle all validation errors
                messages.error(request, str(e))
                # Also add to form errors so they display in the template
                for field, errors in e.message_dict.items():
                    if field == '__all__':  # Non-field errors
                        form.add_error(None, errors[0])
                    else:
                        form.add_error(field, errors[0])
        
        # If form is invalid, add all errors to messages
        for field, errors in form.errors.items():
            if field == '__all__':
                messages.error(request, errors[0])
            else:
                messages.error(request, f"{field.title()}: {errors[0]}")

    else:
        form = StoreForm()

    context = {
        'form': form,
        'creating_store': True,
        'has_existing_store': existing_stores.exists(),
        'has_premium': has_premium,
        'has_active_subscription': has_active_subscription,
    }
    return render(request, 'storefront/store_form.html', context)


@login_required
def store_edit(request, slug):
    """
    Edit an existing store with proper error handling and file uploads.
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    if request.method == 'POST':
        form = StoreForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            try:
                # Full validation including model clean()
                store = form.save(commit=False)
                store.full_clean()
                store.save()

                # Process logo and cover image
                if 'logo' in request.FILES:
                    store.logo = request.FILES['logo']
                if 'cover_image' in request.FILES:
                    store.cover_image = request.FILES['cover_image']
                store.save()

                messages.success(request, 'Store updated successfully!')
                return redirect('storefront:seller_dashboard')

            except ValidationError as e:
                # Handle validation errors
                messages.error(request, str(e))
                # Add to form errors for template display
                for field, errors in e.message_dict.items():
                    if field == '__all__':
                        form.add_error(None, errors[0])
                    else:
                        form.add_error(field, errors[0])
        
        # If form is invalid, add all errors to messages
        for field, errors in form.errors.items():
            if field == '__all__':
                messages.error(request, errors[0])
            else:
                messages.error(request, f"{field.title()}: {errors[0]}")
    else:
        form = StoreForm(instance=store)

    context = {
        'form': form,
        'store': store,
        'creating_store': False,
        'has_premium': store.is_premium,
        'has_active_subscription': Subscription.objects.filter(
            store__owner=request.user,
            status='active'
        ).exists(),
    }
    return render(request, 'storefront/store_form.html', context)


@login_required
def product_create(request, store_slug):
    """
    Create a listing for the user's storefront. Behavior:
    - Enforce a per-user free listing limit (FREE_LISTING_LIMIT).
    - Auto-create a single Store for the user if they don't have one yet.
    - If the provided store_slug doesn't match the user's store, redirect to the correct store slug.
    """
    FREE_LISTING_LIMIT = getattr(settings, 'STORE_FREE_LISTING_LIMIT', 5)

    # Count all listings created by this user (global per-user limit)
    user_listing_count = Listing.objects.filter(seller=request.user).count()

    # Get or create the user's single storefront
    user_store = Store.objects.filter(owner=request.user).first()

    # If user reached limit and is not premium, prompt upgrade
    is_premium = user_store.is_premium if user_store else False
    if not is_premium and user_listing_count >= FREE_LISTING_LIMIT:
        store_for_template = user_store or Store(owner=request.user, name=f"{request.user.username}'s Store", slug=request.user.username)
        messages.warning(request, f"You've reached the free listing limit ({FREE_LISTING_LIMIT}). Upgrade to premium to add more listings.")
        return render(request, 'storefront/confirm_upgrade.html', {
            'store': store_for_template,
            'limit_reached': True,
            'current_count': user_listing_count,
            'free_limit': FREE_LISTING_LIMIT,
        })

    # If the user does not have a store, require they create one first instead of auto-creating it.
    if not user_store:
        messages.info(request, 'Please create a storefront before creating products.')
        return redirect(reverse('storefront:store_create') + '?from=listing')

    # Ensure the route matches the user's storefront; if not, redirect
    if store_slug != user_store.slug:
        return redirect('storefront:product_create', store_slug=user_store.slug)

    store = user_store

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            listing.store = store
            listing.save()
            # Handle multiple uploaded images robustly
            images = request.FILES.getlist('images')
            failed_images = []
            max_size = getattr(settings, 'MAX_IMAGE_UPLOAD_SIZE', 5 * 1024 * 1024)
            for img in images:
                try:
                    # Basic validation: content type and size
                    content_type = getattr(img, 'content_type', '')
                    size = getattr(img, 'size', None)
                    if content_type and not content_type.startswith('image/'):
                        raise ValueError('Invalid file type')
                    if size is not None and size > max_size:
                        raise ValueError('File too large')

                    ListingImage.objects.create(listing=listing, image=img)
                except Exception as e:
                    # Log and track failed image; continue processing
                    failed_images.append({'name': getattr(img, 'name', 'unknown'), 'error': str(e)})

            if failed_images:
                # Keep the listing but inform the user which images failed to upload.
                err_msgs = '; '.join([f"{f['name']}: {f['error']}" for f in failed_images])
                messages.warning(request, f"Listing created but some images failed to upload: {err_msgs}")
            else:
                messages.success(request, 'Listing created successfully')
            return redirect('storefront:store_detail', slug=store.slug)
    else:
        form = ListingForm()

    # Render using the same template as the generic ListingCreateView so users see the identical "Sell Item" form
    categories = Category.objects.filter(is_active=True)
    return render(request, 'listings/listing_form.html', {'form': form, 'store': store, 'categories': categories})


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Listing, pk=pk, seller=request.user)
    if request.method == 'POST':
        # Handle removal of the main listing image via a small separate POST
        if request.POST.get('remove_main_image'):
            # Ensure owner
            if product.seller == request.user:
                if product.image:
                    try:
                        product.image.delete(save=False)
                    except Exception:
                        pass
                    product.image = None
                    product.save()
                    messages.success(request, 'Main image removed successfully.')
                else:
                    messages.info(request, 'No main image to remove.')
            return redirect('storefront:product_edit', pk=product.pk)

        form = ListingForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            listing = form.save(commit=False)
            
            # Ensure the listing has a store associated
            if not listing.store:
                # Try to get the seller's store
                store = Store.objects.filter(owner=listing.seller).first()
                if store:
                    listing.store = store
                else:
                    # Create a new store for the seller if they don't have one
                    store_name = f"{listing.seller.username}'s Store"
                    store_slug = listing.seller.username.lower()
                    store = Store.objects.create(
                        owner=listing.seller,
                        name=store_name,
                        slug=store_slug
                    )
                    listing.store = store
                    messages.info(request, "A new store was created for your listings.")
            
            listing.save()
            
            # Handle additional uploaded images
            images = request.FILES.getlist('images')
            failed_images = []
            max_size = getattr(settings, 'MAX_IMAGE_UPLOAD_SIZE', 5 * 1024 * 1024)
            for img in images:
                try:
                    content_type = getattr(img, 'content_type', '')
                    size = getattr(img, 'size', None)
                    if content_type and not content_type.startswith('image/'):
                        raise ValueError('Invalid file type')
                    if size is not None and size > max_size:
                        raise ValueError('File too large')
                    ListingImage.objects.create(listing=listing, image=img)
                except Exception as e:
                    failed_images.append({'name': getattr(img, 'name', 'unknown'), 'error': str(e)})

            if failed_images:
                err_msgs = '; '.join([f"{f['name']}: {f['error']}" for f in failed_images])
                messages.warning(request, f"Some images failed to upload: {err_msgs}")
            else:
                messages.success(request, "Listing updated successfully!")

            # Redirect to store detail if store exists, otherwise to dashboard
            if listing.store:
                return redirect('storefront:store_detail', slug=listing.store.slug)
            return redirect('storefront:seller_dashboard')
        else:
            # Add form-level error if there are any
            if form.non_field_errors():
                messages.error(request, form.non_field_errors()[0])
            # Add field-specific errors
            for field, errors in form.errors.items():
                messages.error(request, f"{field}: {errors[0]}")
    else:
        form = ListingForm(instance=product)
    
    # Add categories for form and editing flag
    context = {
        'form': form, 
        'product': product,
        'categories': Category.objects.filter(is_active=True),
        'editing': True,
    }
    return render(request, 'listings/listing_form.html', context)


@login_required
def product_delete(request, pk):
    product = get_object_or_404(Listing, pk=pk, seller=request.user)
    store_slug = request.POST.get('store_slug') or (product.seller.stores.first().slug if product.seller.stores.exists() else '')
    if request.method == 'POST':
        product.delete()
        if store_slug:
            return redirect('storefront:store_detail', slug=store_slug)
        return redirect('storefront:seller_dashboard')
    return render(request, 'storefront/product_confirm_delete.html', {'product': product})


@login_required
def image_delete(request, pk):
    # Delete a ListingImage
    img = get_object_or_404(ListingImage, pk=pk)
    # Ensure the requesting user owns the listing
    if img.listing.seller != request.user:
        return redirect('storefront:seller_dashboard')
    if request.method == 'POST':
        # Allow a "next" parameter to return to a specific URL (e.g., edit page)
        next_url = request.POST.get('next') or request.GET.get('next')
        img.delete()
        if next_url:
            # Only allow relative URLs for safety
            if next_url.startswith('/'):
                return redirect(next_url)
        # Fallback to store detail if available
        store_slug = img.listing.store.slug if img.listing.store else (img.listing.seller.stores.first().slug if img.listing.seller.stores.exists() else '')
        if store_slug:
            return redirect('storefront:store_detail', slug=store_slug)
        return redirect('storefront:seller_dashboard')
    return render(request, 'storefront/image_confirm_delete.html', {'image': img})

@login_required
def delete_logo(request, slug):
    """Delete a store's logo."""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    if request.method == 'POST':
        # Delete the actual file
        if store.logo:
            store.logo.delete(save=False)
        store.logo = None
        store.save()
        messages.success(request, 'Store logo removed successfully.')
        return redirect('storefront:store_edit', slug=store.slug)
    return redirect('storefront:store_edit', slug=store.slug)

@login_required
def delete_cover(request, slug):
    """Delete a store's cover image."""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    if request.method == 'POST':
        # Delete the actual file
        if store.cover_image:
            store.cover_image.delete(save=False)
        store.cover_image = None
        store.save()
        messages.success(request, 'Store cover image removed successfully.')
        return redirect('storefront:store_edit', slug=store.slug)
    return redirect('storefront:store_edit', slug=store.slug)


from django.utils import timezone
from datetime import timedelta
from .mpesa import MpesaGateway
from .forms import UpgradeForm
from django.db.models import Q, Sum, Count, Avg
from django.contrib.admin.views.decorators import staff_member_required
from .monitoring import PaymentMonitor
from reviews.models import Review
from listings.models import OrderItem
from .utils import dumps_with_decimals

@login_required
def subscription_manage(request, slug):
    """Subscription management view"""
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    subscription = store.subscriptions.order_by('-started_at').first()
    
    if not subscription:
        messages.warning(request, 'No subscription found for this store.')
        return redirect('storefront:store_upgrade', slug=store.slug)
    
    # Get recent payments
    recent_payments = subscription.payments.order_by('-transaction_date')[:5]
    
    return render(request, 'storefront/subscription_manage.html', {
        'store': store,
        'subscription': subscription,
        'recent_payments': recent_payments,
    })

@login_required
def retry_payment(request, slug):
    """Retry failed payment"""
    if request.method != 'POST':
        return redirect('storefront:subscription_manage', slug=slug)
        
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    subscription = store.subscriptions.order_by('-started_at').first()
    
    if not subscription or subscription.status not in ['past_due', 'trialing']:
        messages.error(request, 'Invalid subscription status for payment retry.')
        return redirect('storefront:subscription_manage', slug=slug)
    
    # Get last known phone number from successful payment
    last_payment = subscription.payments.filter(
        Q(status='completed') | Q(phone_number__isnull=False)
    ).order_by('-transaction_date').first()
    
    if not last_payment or not last_payment.phone_number:
        messages.error(request, 'No payment phone number found. Please upgrade again.')
        return redirect('storefront:store_upgrade', slug=slug)
    
    try:
        # Initialize M-Pesa payment
        mpesa = MpesaGateway()
        # Normalize stored phone number (in case older records used a different format)
        phone_norm = mpesa._normalize_phone(last_payment.phone_number)
        response = mpesa.initiate_stk_push(
            phone=phone_norm,
            amount=999,
            account_reference=f"Store-{store.id}-Retry"
        )
        
        # Create payment record
        MpesaPayment.objects.create(
            subscription=subscription,
            checkout_request_id=response['CheckoutRequestID'],
            merchant_request_id=response['MerchantRequestID'],
            phone_number=phone_norm,
            amount=999,
            status='pending'
        )
        
        messages.success(request, 'Payment initiated. Please complete the M-Pesa payment on your phone.')
        
    except Exception as e:
        messages.error(request, f'Failed to initiate payment: {str(e)}')
    
    return redirect('storefront:subscription_manage', slug=slug)

@login_required
def cancel_subscription(request, slug):
    """Cancel subscription"""
    if request.method != 'POST':
        return redirect('storefront:subscription_manage', slug=slug)
        
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    subscription = store.subscriptions.order_by('-started_at').first()
    
    if not subscription or not subscription.is_active():
        messages.error(request, 'No active subscription found.')
        return redirect('storefront:subscription_manage', slug=slug)
    
    try:
        subscription.cancel()
        messages.success(request, 'Subscription cancelled successfully. Premium features will be available until the end of your current billing period.')
    except Exception as e:
        messages.error(request, f'Failed to cancel subscription: {str(e)}')
    
    return redirect('storefront:subscription_manage', slug=slug)

@staff_member_required
def payment_monitor(request):
    """Admin view for monitoring payment system health.

    Supports time periods via ?period=24h|7d|30d|all and sends email alerts
    to ADMINS for critical conditions.
    """
    monitor = PaymentMonitor()
    
    # Determine time period
    period = request.GET.get('period', '24h')
    time_period = None
    if period == '24h':
        time_period = timedelta(hours=24)
    elif period == '7d':
        time_period = timedelta(days=7)
    elif period == '30d':
        time_period = timedelta(days=30)
    # else 'all' -> time_period stays None

    # Gather metrics
    success_rate = monitor.get_payment_success_rate(time_period)
    failed_payments = monitor.get_failed_payments()
    subscription_metrics = monitor.get_subscription_metrics(time_period)

    alerts = []

    # Payment success rate alerting
    if success_rate < 70:
        severity = 'critical' if success_rate < 50 else 'warning'
        alerts.append({
            'message': f'Payment success rate low: {success_rate:.1f}%',
            'severity': severity,
            'timestamp': timezone.now()
        })
        # Send email on critical
        if severity == 'critical':
            try:
                from .alerts import send_admin_alert
                send_admin_alert(
                    subject=f"Critical: Low payment success rate {success_rate:.1f}%",
                    message=f"Payment success rate for period {period} is {success_rate:.1f}%. Please investigate."
                )
            except Exception:
                # Don't raise in view; just log via logger configured elsewhere
                pass

    # Past due subscriptions
    past_due = subscription_metrics.get('past_due_subscriptions', 0)
    if past_due > 10:
        severity = 'critical' if past_due > 20 else 'warning'
        alerts.append({
            'message': f'High number of past due subscriptions: {past_due}',
            'severity': severity,
            'timestamp': timezone.now()
        })
        if severity == 'critical':
            try:
                from .alerts import send_admin_alert
                send_admin_alert(
                    subject=f"Critical: High past due subscriptions ({past_due})",
                    message=f"There are {past_due} past-due subscriptions. Please review billing and customer outreach."
                )
            except Exception:
                pass

    # Trial conversion / churn alerts (warning level)
    if subscription_metrics.get('trial_conversion_rate', 100) < 30:
        alerts.append({
            'message': f"Low trial conversion rate: {subscription_metrics.get('trial_conversion_rate', 0):.1f}%",
            'severity': 'warning',
            'timestamp': timezone.now()
        })

    if subscription_metrics.get('churn_rate', 0) > 5:
        severity = 'critical' if subscription_metrics.get('churn_rate') > 10 else 'warning'
        alerts.append({
            'message': f"High churn rate: {subscription_metrics.get('churn_rate'):.1f}%",
            'severity': severity,
            'timestamp': timezone.now()
        })
        if severity == 'critical':
            try:
                from .alerts import send_admin_alert
                send_admin_alert(
                    subject=f"Critical: High churn rate {subscription_metrics.get('churn_rate'):.1f}%",
                    message=f"Churn rate has exceeded acceptable threshold: {subscription_metrics.get('churn_rate'):.1f}%"
                )
            except Exception:
                pass

    # Prepare context for template (use enhanced template)
    daily_trends = subscription_metrics.get('daily_trends', [])
    avg_daily_subscriptions = 0
    if daily_trends:
        try:
            avg_daily_subscriptions = sum(d['new_subscriptions'] for d in daily_trends) / len(daily_trends)
        except Exception:
            avg_daily_subscriptions = 0

    context = {
        'period': period,
        'success_rate': success_rate,
        'failed_payments': failed_payments,
        'alerts': sorted(alerts, key=lambda x: x.get('severity') == 'critical', reverse=True),
        'avg_daily_subscriptions': avg_daily_subscriptions,
        'daily_trends': daily_trends,
        **subscription_metrics
    }

    return render(request, 'storefront/payment_monitor_enhanced.html', context)

@login_required
def seller_analytics(request):
    """
    Seller analytics dashboard showing aggregated metrics across all stores.
    """
    # Get all stores owned by the user
    stores = Store.objects.filter(owner=request.user)
    
    # Get time period from query params
    period = request.GET.get('period', '24h')
    time_period = None
    previous_period = None
    
    if period == '24h':
        time_period = timezone.now() - timedelta(hours=24)
        previous_period = timezone.now() - timedelta(hours=48)
    elif period == '7d':
        time_period = timezone.now() - timedelta(days=7)
        previous_period = timezone.now() - timedelta(days=14)
    elif period == '30d':
        time_period = timezone.now() - timedelta(days=30)
        previous_period = timezone.now() - timedelta(days=60)
    
    # Base queryset for orders across all stores
    orders_qs = OrderItem.objects.filter(listing__store__in=stores)
    
    # Current period metrics
    if time_period:
        current_orders = orders_qs.filter(added_at__gte=time_period)
        current_revenue = current_orders.aggregate(
            total=Sum('price', default=0)
        )['total']
        current_order_count = current_orders.count()
        
        # Previous period for trend calculation
        previous_orders = orders_qs.filter(
            added_at__gte=previous_period,
            added_at__lt=time_period
        )
        previous_revenue = previous_orders.aggregate(
            total=Sum('price', default=0)
        )['total']
        previous_order_count = previous_orders.count()
        
        # Calculate trends
        revenue_trend = (
            ((current_revenue - previous_revenue) / previous_revenue * 100)
            if previous_revenue else 0
        )
        orders_trend = (
            ((current_order_count - previous_order_count) / previous_order_count * 100)
            if previous_order_count else 0
        )
    else:
        # All time metrics
        current_revenue = orders_qs.aggregate(
            total=Sum('price', default=0)
        )['total']
        current_order_count = orders_qs.count()
        revenue_trend = 0
        orders_trend = 0
    
    # Store metrics
    active_stores = stores.count()
    premium_stores = stores.filter(is_premium=True).count()
    active_listings = Listing.objects.filter(
        store__in=stores,
        is_active=True
    ).count()
    
    # Revenue & Orders trend data
    trend_days = 30 if period == '30d' else (7 if period == '7d' else 1)
    revenue_data = []
    orders_data = []
    labels = []
    
    for i in range(trend_days):
        day = timezone.now() - timedelta(days=i)
        day_orders = orders_qs.filter(added_at__date=day.date())
        
        revenue = day_orders.aggregate(
            total=Sum('price', default=0)
        )['total']
        orders = day_orders.count()
        
        revenue_data.insert(0, revenue)
        orders_data.insert(0, orders)
        labels.insert(0, day.strftime('%b %d'))
    
    revenue_orders_trend_data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Revenue',
                'data': revenue_data,
                'borderColor': '#4CAF50',
                'yAxisID': 'y',
            },
            {
                'label': 'Orders',
                'data': orders_data,
                'borderColor': '#2196F3',
                'yAxisID': 'y1',
            }
        ]
    }
    
    # Store performance distribution
    store_performance = []
    for store in stores:
        store_revenue = orders_qs.filter(
            listing__store=store
        ).aggregate(total=Sum('price', default=0))['total']
        store_performance.append({
            'name': store.name,
            'revenue': store_revenue
        })
    
    store_performance.sort(key=lambda x: x['revenue'], reverse=True)
    store_performance_data = {
        'labels': [s['name'] for s in store_performance],
        'datasets': [{
            'data': [s['revenue'] for s in store_performance],
            'backgroundColor': [
                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
            ]
        }]
    }
    
    # Top performing stores
    top_stores = []
    for store in stores:
        store_orders = orders_qs.filter(listing__store=store)
        store_revenue = store_orders.aggregate(
            total=Sum('price', default=0)
        )['total']
        
        # Calculate average rating
        store_ratings = Review.objects.filter(
            seller=store.owner
        ).aggregate(avg_rating=Avg('rating', default=0))
        
        top_stores.append({
            'name': store.name,
            'slug': store.slug,
            'revenue': store_revenue,
            'orders': store_orders.count(),
            'rating': store_ratings['avg_rating']
        })
    
    top_stores.sort(key=lambda x: x['revenue'], reverse=True)
    
    # Top categories
    top_categories = []
    categories = Category.objects.filter(
        listing__store__in=stores
    ).distinct()
    
    for category in categories:
        category_orders = orders_qs.filter(
            listing__category=category
        )
        revenue = category_orders.aggregate(
            total=Sum('price', default=0)
        )['total']
        
        top_categories.append({
            'name': category.name,
            'revenue': revenue,
            'orders': category_orders.count(),
            'listings': Listing.objects.filter(
                store__in=stores,
                category=category,
                is_active=True
            ).count()
        })
    
    top_categories.sort(key=lambda x: x['revenue'], reverse=True)
    top_categories = top_categories[:5]
    
    # Recent activity across all stores
    recent_activity = []
    
    # Recent orders
    recent_orders = orders_qs.order_by('-added_at')[:5]
    for order in recent_orders:
        recent_activity.append({
            'timestamp': order.added_at,
            'store': order.listing.store.name,
            'type': 'Order',
            'description': f'New order for {order.listing.title}'
        })
    
    # Recent reviews
    recent_reviews = Review.objects.filter(
        seller__in=[store.owner for store in stores]
    ).order_by('-date_created')[:5]
    
    for review in recent_reviews:
        recent_activity.append({
            'timestamp': review.date_created,
            'store': review.seller.stores.first().name if review.seller.stores.exists() else 'Unknown Store',
            'type': 'Review',
            'description': f'{review.rating}★ review by {review.reviewer.username}'
        })
    
    # Recent listings
    recent_listings = Listing.objects.filter(
        store__in=stores
    ).order_by('-date_created')[:5]
    
    for listing in recent_listings:
        recent_activity.append({
            'timestamp': listing.date_created,
            'store': listing.store.name,
            'type': 'Listing',
            'description': f'New listing: {listing.title}'
        })
    
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:10]
    
    # Customer location data
    customer_locations = orders_qs.values(
        'order__city'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    customer_map_data = {
        'labels': [loc['order__city'] for loc in customer_locations],
        'datasets': [{
            'data': [loc['count'] for loc in customer_locations],
            'backgroundColor': [
                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
            ]
        }]
    }
    
    context = {
        'period': period,
        'total_revenue': current_revenue,
        'total_orders': current_order_count,
        'revenue_trend': round(revenue_trend, 1),
        'orders_trend': round(orders_trend, 1),
        'active_stores': active_stores,
        'premium_stores': premium_stores,
        'active_listings': active_listings,
        'revenue_orders_trend_data': dumps_with_decimals(revenue_orders_trend_data),
        'store_performance_data': dumps_with_decimals(store_performance_data),
        'top_stores': top_stores[:5],
        'top_categories': top_categories,
        'recent_activity': recent_activity,
        'customer_map_data': dumps_with_decimals(customer_map_data)
    }
    
    return render(request, 'storefront/seller_analytics.html', context)

@login_required
def store_analytics(request, slug):
    """
    Store analytics view with comprehensive metrics and visualizations.
    """
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    # Get time period from query params
    period = request.GET.get('period', '24h')
    time_period = None
    
    if period == '24h':
        time_period = timezone.now() - timedelta(hours=24)
    elif period == '7d':
        time_period = timezone.now() - timedelta(days=7)
    elif period == '30d':
        time_period = timezone.now() - timedelta(days=30)
    
    # Base queryset for the store's listings
    listings_qs = Listing.objects.filter(store=store)
    orders_qs = OrderItem.objects.filter(listing__store=store)
    
    if time_period:
        orders_qs = orders_qs.filter(added_at__gte=time_period)
    
    # Basic metrics
    revenue = orders_qs.aggregate(
        total=Sum('price', default=0)
    )['total']
    
    orders_count = orders_qs.count()
    active_listings = listings_qs.filter(is_active=True).count()
    avg_order_value = orders_qs.aggregate(
        avg=Avg('price', default=0)
    )['avg']
    
    # Revenue trend (daily data points)
    trend_days = 30 if period == '30d' else (7 if period == '7d' else 1)
    revenue_trend = []
    labels = []
    
    for i in range(trend_days):
        day = timezone.now() - timedelta(days=i)
        day_revenue = orders_qs.filter(
            added_at__date=day.date()
        ).aggregate(total=Sum('price', default=0))['total']
        
        revenue_trend.insert(0, day_revenue)
        labels.insert(0, day.strftime('%b %d'))
    
    revenue_trend_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Daily Revenue',
            'data': revenue_trend,
            'fill': False,
            'borderColor': '#4CAF50',
            'tension': 0.1
        }]
    }
    
    # Top categories by sales
    category_sales = orders_qs.values(
        'listing__category__name'
    ).annotate(
        total_sales=Count('id'),
        revenue=Sum('price')
    ).order_by('-total_sales')[:5]
    
    category_data = {
        'labels': [item['listing__category__name'] for item in category_sales],
        'datasets': [{
            'data': [item['total_sales'] for item in category_sales],
            'backgroundColor': [
                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
            ]
        }]
    }
    
    # Top performing products
    top_products = orders_qs.values(
        'listing__title'
    ).annotate(
        sales_count=Count('id'),
        revenue=Sum('price')
    ).order_by('-revenue')[:5]
    
    # Recent activity (orders, reviews, listings)
    recent_activity = []
    
    # Add recent orders
    recent_orders = orders_qs.order_by('-added_at')[:5]
    for order in recent_orders:
        recent_activity.append({
            'timestamp': order.added_at,
            'type': 'Order',
            'description': f'New order for {order.listing.title}'
        })
    
    # Add recent reviews
    recent_reviews = Review.objects.filter(
        seller=store.owner
    ).order_by('-date_created')[:5]
    
    for review in recent_reviews:
        recent_activity.append({
            'timestamp': review.date_created,
            'type': 'Review',
            'description': f'{review.rating}★ review by {review.reviewer.username}'
        })
    
    # Add recent listings
    recent_listings = listings_qs.order_by('-date_created')[:5]
    for listing in recent_listings:
        recent_activity.append({
            'timestamp': listing.date_created,
            'type': 'Listing',
            'description': f'New listing: {listing.title}'
        })
    
    # Sort combined activity by timestamp
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:10]  # Keep top 10
    
    # Customer demographics (if we have user data)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    buyer_ages = (
        User.objects.filter(
            orders__order_items__listing__store=store,
            date_of_birth__isnull=False
        )
        .values('date_of_birth')
        .annotate(count=Count('id'))
        .order_by('date_of_birth')
    )
    
    age_ranges = ['18-24', '25-34', '35-44', '45-54', '55+']
    age_data = [0] * len(age_ranges)
    
    for buyer in buyer_ages:
        age = (timezone.now().date() - buyer['date_of_birth']).days // 365
        if age < 25:
            age_data[0] += buyer['count']
        elif age < 35:
            age_data[1] += buyer['count']
        elif age < 45:
            age_data[2] += buyer['count']
        elif age < 55:
            age_data[3] += buyer['count']
        else:
            age_data[4] += buyer['count']
    
    demographics_data = {
        'labels': age_ranges,
        'datasets': [{
            'label': 'Buyers by Age Range',
            'data': age_data,
            'backgroundColor': '#4CAF50'
        }]
    }
    
    # Customer locations
    locations = orders_qs.values(
        'order__city'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    locations_data = {
        'labels': [loc['order__city'] for loc in locations],
        'datasets': [{
            'data': [loc['count'] for loc in locations],
            'backgroundColor': [
                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
            ]
        }]
    }
    
    context = {
        'store': store,
        'period': period,
        'revenue': revenue,
        'orders_count': orders_count,
        'active_listings': active_listings,
        'avg_order_value': avg_order_value,
        'revenue_trend_data': dumps_with_decimals(revenue_trend_data),
        'category_data': dumps_with_decimals(category_data),
        'top_products': top_products,
        'recent_activity': recent_activity,
        'demographics_data': dumps_with_decimals(demographics_data),
        'locations_data': dumps_with_decimals(locations_data),
    }
    
    return render(request, 'storefront/store_analytics.html', context)

@login_required
def store_upgrade(request, slug):
    store = get_object_or_404(Store, slug=slug, owner=request.user)
    
    if request.method == 'POST':
        form = UpgradeForm(request.POST)
        if not form.is_valid():
            # Form-level validation will provide user-friendly feedback
            return render(request, 'storefront/confirm_upgrade.html', {'store': store, 'form': form})

        phone_number = form.cleaned_data['phone_number']

        try:
            mpesa = MpesaGateway()

            # Reuse existing trialing subscription if present, otherwise create one
            subscription = Subscription.objects.filter(store=store, status='trialing').first()
            if not subscription:
                subscription = Subscription.objects.create(
                    store=store,
                    plan='premium',
                    status='trialing',
                    trial_ends_at=timezone.now() + timedelta(days=7)
                )

            # Initiate M-Pesa payment (phone already normalized by form)
            response = mpesa.initiate_stk_push(
                phone=phone_number,
                amount=999,  # KSh 999 as shown in template
                account_reference=f"Store-{store.id}"
            )

            # Create payment record
            MpesaPayment.objects.create(
                subscription=subscription,
                checkout_request_id=response['CheckoutRequestID'],
                merchant_request_id=response['MerchantRequestID'],
                phone_number=phone_number,
                amount=999,
                status='pending'
            )

            # Activate store premium features for trial period
            store.is_premium = True
            store.save()

            messages.success(request, 'Payment initiated. Please complete the M-Pesa payment on your phone.')
            return redirect('storefront:seller_dashboard')

        except Exception as e:
            messages.error(request, f'Payment initiation failed: {str(e)}')
            return render(request, 'storefront/confirm_upgrade.html', {'store': store})

    else:
        form = UpgradeForm()

    return render(request, 'storefront/confirm_upgrade.html', {'store': store, 'form': form})
