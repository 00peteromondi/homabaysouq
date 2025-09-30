# listings/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q, Count, Avg
from .models import Listing, Category, Favorite, Activity
from .forms import ListingForm
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q
from blog.models import BlogPost


from notifications.utils import (
    notify_new_order, notify_order_shipped, notify_order_delivered,
    notify_payment_received, notify_listing_favorited, notify_new_review
)


User = get_user_model()

class ListingListView(ListView):
    model = Listing
    template_name = 'listings/home.html'
    context_object_name = 'listings'
    paginate_by = 12

    def get_queryset(self):
        queryset = Listing.objects.filter(is_sold=False).order_by('-date_created')
        
        # Search functionality
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | 
                Q(description__icontains=query)
            )
        
        # Filter by location
        location = self.request.GET.get('location')
        if location:
            queryset = queryset.filter(location=location)
        
        # Filter by category
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category__id=category_id)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['locations'] = Listing.HOMABAY_LOCATIONS
        context['total_listings_count'] = Listing.objects.filter(is_sold=False).count()
        context['total_users_count'] = User.objects.count()
        context['total_categories_count'] = Category.objects.count()
        try:
            from blog.models import BlogPost
            context['blog_posts'] = BlogPost.objects.filter(
                status='published'
            ).select_related('author').order_by('-published_at')[:3]
        except Exception as e:
            print(f"Error loading blog posts: {e}")
            context['blog_posts'] = []
        
        
        # Add the missing context variables that home.html expects
        context['popular_categories'] = Category.objects.annotate(
            listing_count=Count('listing')
        ).order_by('-listing_count')[:6]
        
        # Add placeholder values for missing variables
        context['total_messages_count'] = 0  # Replace with actual count if you have messages
        # Get completed transactions count (orders with status 'delivered')
        try:
            from .models import Order
            context['successful_transactions'] = Order.objects.filter(
                status__in=['paid', 'shipped', 'delivered']
            ).count()
        except Exception as e:
            print(f"Error loading completed transactions: {e}")
            context['successful_transactions'] = 0
        
        # Alternative: Count all paid orders (if you want to include shipped orders too)
        

        # For testimonials - create empty list since you don't have testimonials model
        context['testimonials'] = []
        
        # Efficiently get listing counts per category
        category_counts = (
            Listing.objects.filter(is_sold=False)
            .values('category')
            .annotate(count=Count('id'))
        )
        # Build a dict: {category_id: count}
        listings_count = {cat['category']: cat['count'] for cat in category_counts}
        # Ensure all categories are present, even if count is 0
        for category in Category.objects.all():
            listings_count.setdefault(category.id, 0)
        context['listings_count'] = listings_count

        context['recent_activities'] = Activity.objects.select_related('user').order_by('-timestamp')[:5]

        category_id = self.request.GET.get('category')
        if category_id:
            context['selected_category'] = get_object_or_404(Category, id=category_id)

        return context

from django.db.models import Avg, Count
from django.views.generic import DetailView
from django.shortcuts import get_object_or_404
from .models import Listing, Favorite, Review

class ListingDetailView(DetailView):
    model = Listing
    template_name = 'listings/listing_detail.html'
    context_object_name = 'listing'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        listing = self.get_object()
        user = self.request.user
        
        # Get all reviews for the listing (available to all users)
        context['reviews'] = listing.reviews.select_related('user').all()
        
        # Calculate average rating (available to all users)
        avg_rating = listing.reviews.aggregate(
            avg_rating=Avg('rating')
        )['avg_rating']
        context['avg_rating'] = round(avg_rating, 1) if avg_rating else 0
        
        # Check if the current user has favorited this listing (only for authenticated users)
        if user.is_authenticated:
            context['is_favorited'] = Favorite.objects.filter(
                user=user, 
                listing=listing
            ).exists()
        else:
            context['is_favorited'] = False
            
        return context
        
class ListingCreateView(LoginRequiredMixin, CreateView):
    model = Listing
    form_class = ListingForm

    def form_valid(self, form):
        form.instance.seller = self.request.user
        return super().form_valid(form)

class ListingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Listing
    form_class = ListingForm

    

    def test_func(self):
        listing = self.get_object()
        return self.request.user == listing.seller

class ListingDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Listing
    success_url = '/'

    def test_func(self):
        listing = self.get_object()
        return self.request.user == listing.seller


def all_listings(request):
    # Get all non-sold listings
    listings = Listing.objects.filter(is_sold=False).order_by('-date_created')
    
    # Get filter parameters
    category_id = request.GET.get('category')
    location = request.GET.get('location')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    search_query = request.GET.get('q')
    sort_by = request.GET.get('sort_by', 'newest')
    
    # Apply filters
    if category_id and category_id != 'all':
        listings = listings.filter(category__id=category_id)
    
    if location and location != 'all':
        listings = listings.filter(location=location)
    
    if min_price:
        listings = listings.filter(price__gte=min_price)
    
    if max_price:
        listings = listings.filter(price__lte=max_price)
    
    if search_query:
        listings = listings.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by == 'price_low':
        listings = listings.order_by('price')
    elif sort_by == 'price_high':
        listings = listings.order_by('-price')
    elif sort_by == 'oldest':
        listings = listings.order_by('date_created')
    else:  # newest is default
        listings = listings.order_by('-date_created')
    
    # Pagination
    paginator = Paginator(listings, 12)  # Show 12 listings per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # For AJAX requests, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        listings_data = []
        for listing in page_obj:
            listings_data.append({
                'id': listing.id,
                'title': listing.title,
                'price': str(listing.price),
                'image_url': listing.image.url,
                'category': listing.category.name,
                'location': listing.get_location_display(),
                'date_created': listing.date_created.strftime('%b %d, %Y'),
                'url': listing.get_absolute_url(),
            })
        
        return JsonResponse({
            'listings': listings_data,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'current_page': page_obj.number,
            'num_pages': paginator.num_pages,
            'total_count': paginator.count,
        })
    
    # For regular requests, return the full page
    context = {
        'listings': page_obj,
        'categories': Category.objects.all(),
        'locations': Listing.HOMABAY_LOCATIONS,
        'selected_category': category_id,
        'selected_location': location,
        'min_price': min_price,
        'max_price': max_price,
        'search_query': search_query,
        'sort_by': sort_by,
        'total_listings_count': listings.count(),
    }
    
    return render(request, 'listings/all_listings.html', context)


@login_required
@require_POST
def toggle_favorite(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id)
    favorite, created = Favorite.objects.get_or_create(
        user=request.user, 
        listing=listing
    )
    
    if not created:
        favorite.delete()
        is_favorited = False
    else:
        is_favorited = True
        # Notify seller about favorite
        if listing.seller != request.user:
            notify_listing_favorited(listing.seller, request.user, listing)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'is_favorited': is_favorited,
            'favorite_count': listing.favorited_by.count()
        })
    
    return redirect('listing-detail', pk=listing_id)

@login_required
def favorite_listings(request):
    favorites = Favorite.objects.filter(user=request.user).select_related('listing')
    return render(request, 'listings/favorites.html', {'favorites': favorites})

@login_required
def my_listings(request):
    listings = Listing.objects.filter(seller=request.user).order_by('-date_created')
    return render(request, 'listings/my_listings.html', {'listings': listings})

# In your listings/views.py
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone
from .models import Cart, CartItem, Order, OrderItem, Payment, Escrow, Listing
from .forms import CheckoutForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json


@login_required
def unread_notifications_count(request):
    """API endpoint to get unread notifications count"""
    # You'll need to implement your notifications system
    # For now, returning a placeholder
    unread_count = 0  # Replace with actual notification count logic
    return JsonResponse({'count': unread_count})

@login_required
@require_POST
def update_cart_item(request, item_id):
    """AJAX endpoint for updating cart item quantity"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    
    # Check if quantity doesn't exceed available stock
    if quantity > cart_item.listing.stock:
        return JsonResponse({
            'success': False,
            'error': f"Only {cart_item.listing.stock} units available."
        })
    
    if quantity <= 0:
        cart_item.delete()
        success = True
        item_count = request.user.cart.items.count() if hasattr(request.user, 'cart') else 0
    else:
        cart_item.quantity = quantity
        cart_item.save()
        success = True
        item_count = request.user.cart.items.count() if hasattr(request.user, 'cart') else 0
    
    cart_total = request.user.cart.get_total_price() if hasattr(request.user, 'cart') else 0
    
    return JsonResponse({
        'success': success,
        'cart_total': float(cart_total),
        'item_count': item_count
    })
@login_required
@require_POST
def remove_from_cart(request, item_id):
    """AJAX endpoint for removing cart items"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_item.delete()
    
    item_count = request.user.cart.items.count() if hasattr(request.user, 'cart') else 0
    cart_total = request.user.cart.get_total_price() if hasattr(request.user, 'cart') else 0
    
    return JsonResponse({
        'success': True,
        'cart_total': float(cart_total),
        'item_count': item_count
    })

@login_required
@require_POST
def clear_cart(request):
    """Clear entire cart"""
    cart = get_object_or_404(Cart, user=request.user)
    cart.items.all().delete()
    
    return JsonResponse({'success': True})

# Update the existing view_cart function to handle AJAX
@login_required
def view_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    # Handle AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart_data = {
            'items': [],
            'total_price': float(cart.get_total_price()),
            'item_count': cart.items.count()
        }
        
        for item in cart.items.all():
            cart_data['items'].append({
                'id': item.id,
                'listing': {
                    'id': item.listing.id,
                    'title': item.listing.title,
                    'price': float(item.listing.price),
                    'image_url': item.listing.image.url,
                    'category': item.listing.category.name
                },
                'quantity': item.quantity,
                'total_price': float(item.get_total_price())
            })
        
        return JsonResponse(cart_data)
    
    return render(request, 'listings/cart.html', {'cart': cart})

# Update the add_to_cart function for AJAX
@login_required
def add_to_cart(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id, is_sold=False)
    
    # Check if item is in stock
    if listing.stock <= 0:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': "This item is out of stock."})
        messages.warning(request, "This item is out of stock.")
        return redirect('listing-detail', pk=listing_id)
    
    # Users shouldn't add their own listings to cart
    if listing.seller == request.user:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': "You cannot add your own listing to cart."})
        messages.warning(request, "You cannot add your own listing to cart.")
        return redirect('listing-detail', pk=listing_id)
    
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        listing=listing,
        defaults={'quantity': 1}
    )
    
    if not created:
        # Check if we're not exceeding available stock
        if cart_item.quantity + 1 > listing.stock:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': f"Only {listing.stock} units available."})
            messages.warning(request, f"Only {listing.stock} units of '{listing.title}' are available.")
            return redirect('listing-detail', pk=listing_id)
        
        cart_item.quantity += 1
        cart_item.save()
        message = f"Updated quantity of {listing.title} in your cart."
    else:
        message = f"Added {listing.title} to your cart."
    
    # Handle AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': message,
            'cart_total': float(cart.get_total_price()),
            'item_count': cart.items.count()
        })
    
    messages.success(request, message)
    return redirect('listing-detail', pk=listing_id)

@login_required
def checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    
    for cart_item in cart.items.all():
        if cart_item.quantity > cart_item.listing.stock:
            messages.error(request, f"Sorry, only {cart_item.listing.stock} units of '{cart_item.listing.title}' are available.")
            return redirect('view_cart')
    
    
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create order
                    order = Order.objects.create(
                        user=request.user,
                        total_price=cart.get_total_price(),
                        # Add form data to order
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name'],
                        email=form.cleaned_data['email'],
                        phone_number=form.cleaned_data['phone_number'],
                        shipping_address=form.cleaned_data['shipping_address'],
                        city=form.cleaned_data['city'],
                        postal_code=form.cleaned_data['postal_code'],
                    )
                    
                    # Create order items
                    for cart_item in cart.items.all():
                        OrderItem.objects.create(
                            order=order,
                            listing=cart_item.listing,
                            quantity=cart_item.quantity,
                            price=cart_item.listing.price
                        )
                    
                    # Create payment record
                    payment = Payment.objects.create(
                        order=order,
                        amount=order.total_price
                    )
                    
                    # Create escrow record
                    Escrow.objects.create(
                        order=order,
                        amount=order.total_price
                    )
                    
                    # Clear cart
                    cart.items.all().delete()
                    
                    messages.success(request, "Order created successfully! Please complete payment.")
                    return redirect('process_payment', order_id=order.id)
                    
            except Exception as e:
                messages.error(request, f"An error occurred during checkout: {str(e)}")
                # Return the form with errors instead of falling through
                return render(request, 'listings/checkout.html', {
                    'cart': cart,
                    'form': form
                })
        else:
            # Form is invalid, return with errors
            return render(request, 'listings/checkout.html', {
                'cart': cart,
                'form': form
            })
    else:
        # GET request - show empty form
        form = CheckoutForm()
    
    # Ensure we always return an HttpResponse
    return render(request, 'listings/checkout.html', {
        'cart': cart,
        'form': form
    })

@login_required
def process_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status != 'pending':
        messages.warning(request, "This order has already been processed.")
        return redirect('order_detail', order_id=order.id)
    
    if request.method == 'POST':
        try:
            # Simulate successful payment
            transaction_id = f"TXN{order.id}{int(timezone.now().timestamp())}"
            order.payment.mark_as_completed(transaction_id)

            for order_item in order.order_items.all():
                notify_payment_received(order_item.listing.seller, request.user, order)




            # Create activity log
            Activity.objects.create(
                user=request.user,
                action=f"Payment completed for Order #{order.id}"
            )
            
            messages.success(request, "Payment completed successfully! The seller will now prepare your order.")
            return redirect('order_detail', order_id=order.id)
            
        except Exception as e:
            messages.error(request, f"Payment failed: {str(e)}")
    
    return render(request, 'listings/payment.html', {'order': order})


@login_required
def order_list(request):
    """Show orders where user is either buyer or seller"""
    # Get filter parameters
    status_filter = request.GET.get('status')
    role_filter = request.GET.get('role')
    
    # Base queries
    buyer_orders = Order.objects.filter(user=request.user)
    seller_orders = Order.objects.filter(order_items__listing__seller=request.user)
    
    # Apply status filter if provided
    if status_filter and status_filter != 'all':
        buyer_orders = buyer_orders.filter(status=status_filter)
        seller_orders = seller_orders.filter(status=status_filter)
    
    # Apply role filter if provided
    if role_filter == 'buyer':
        all_orders = buyer_orders.distinct()
    elif role_filter == 'seller':
        all_orders = seller_orders.distinct()
    else:
        # Combine using union (proper way to combine distinct queries)
        all_orders = buyer_orders.union(seller_orders).order_by('-created_at')
    
    # Ensure proper ordering
    all_orders = all_orders.order_by('-created_at')
    
    # Get counts for display
    buyer_orders_count = buyer_orders.count()
    seller_orders_count = seller_orders.distinct().count()
    
    # Paginate
    paginator = Paginator(all_orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'orders': page_obj,
        'status_filter': status_filter,
        'role_filter': role_filter,
        'buyer_orders_count': buyer_orders_count,
        'seller_orders_count': seller_orders_count,
        'total_orders_count': buyer_orders_count + seller_orders_count,
    }
    
    return render(request, 'listings/order_list.html', context)

@login_required
def order_detail(request, order_id):
    """Order detail view that works for both buyers and sellers"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if user has permission to view this order
    if order.user != request.user and not order.order_items.filter(listing__seller=request.user).exists():
        messages.error(request, "You don't have permission to view this order.")
        return redirect('order_list')
    
    # Determine user's role in this order
    is_buyer = order.user == request.user
    is_seller = order.order_items.filter(listing__seller=request.user).exists()
    
    # Get items relevant to the user
    if is_seller:
        # Show only items that belong to this seller
        order_items = order.order_items.filter(listing__seller=request.user)
    else:
        # Show all items for buyer
        order_items = order.order_items.all()
    
    context = {
        'order': order,
        'order_items': order_items,
        'is_buyer': is_buyer,
        'is_seller': is_seller,
        'can_ship': is_seller and order.status == 'paid',
        'can_confirm': is_buyer and order.status == 'shipped',
        'can_dispute': is_buyer and order.status in ['shipped', 'delivered'],
    }
    
    return render(request, 'listings/order_detail.html', context)
# Seller views
@login_required
def seller_orders(request):
    # Get all orders that contain listings from this seller
    orders = Order.objects.filter(
        order_items__listing__seller=request.user
    ).distinct().order_by('-created_at')
    
    return render(request, 'listings/seller_orders.html', {'orders': orders})

@login_required
def mark_order_shipped(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Check if the user is the seller of any item in this order
    if not order.order_items.filter(listing__seller=request.user).exists():
        messages.error(request, "You don't have permission to modify this order.")
        return redirect('seller_orders')
    
    if order.status != 'paid':
        messages.warning(request, "Only paid orders can be marked as shipped.")
        return redirect('seller_orders')
    
    order.status = 'shipped'
    order.save()
    
    # Notify buyer
    notify_order_shipped(order.user, request.user, order)
    
    # Create activity log
    Activity.objects.create(
        user=request.user,
        action=f"Order #{order.id} marked as shipped"
    )
    
    messages.success(request, f"Order #{order.id} marked as shipped.")
    return redirect('seller_orders')

# Update confirm_delivery to notify seller
@login_required
def confirm_delivery(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status != 'shipped':
        messages.warning(request, "This order has not been shipped yet.")
        return redirect('order_detail', order_id=order.id)
    
    order.status = 'delivered'
    order.delivered_at = timezone.now()
    order.save()
    
    # Notify sellers
    for order_item in order.order_items.all():
        notify_order_delivered(order_item.listing.seller, request.user, order)
    
    # Release escrow funds to seller
    order.escrow.release_funds()
    
    # Create activity log
    Activity.objects.create(
        user=request.user,
        action=f"Order #{order.id} delivered and confirmed"
    )
    
    messages.success(request, "Thank you for confirming delivery! Funds have been released to the seller.")
    return redirect('order_detail', order_id=order.id)

@login_required
def create_dispute(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if order.status not in ['shipped', 'delivered']:
        messages.warning(request, "You can only dispute orders that have been shipped or delivered.")
        return redirect('order_detail', order_id=order.id)
    
    order.status = 'disputed'
    order.save()
    
    order.escrow.status = 'disputed'
    order.escrow.save()
    
    # Create activity log
    Activity.objects.create(
        user=request.user,
        action=f"Dispute created for Order #{order.id}"
    )
    
    messages.info(request, "Dispute created. Our team will review your case and contact you shortly.")
    return redirect('order_detail', order_id=order.id)


from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Review, Order
from .forms import ReviewForm

@login_required
def leave_review(request, listing_id=None, seller_id=None):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if listing_id:
        listing = get_object_or_404(Listing, id=listing_id)
        seller = listing.seller

        if request.user == seller:
            messages.error(request, "You cannot review your own listing.")
            return redirect('listing-detail', pk=listing.id)

        existing_review = Review.objects.filter(
            user=request.user,
            listing=listing
        ).first()

        if request.method == 'POST':
            form = ReviewForm(request.POST, instance=existing_review)
            if form.is_valid():
                review = form.save(commit=False)
                review.user = request.user
                review.listing = listing
                review.save()
                
                # Notify seller about the new review
                notify_new_review(seller, request.user, review, listing)
                
                messages.success(request, "Thank you for your review!")
                return redirect('listing-detail', pk=listing.id)
        else:
            form = ReviewForm(instance=existing_review)

        return render(request, 'reviews/create_review.html', {
            'form': form,
            'listing': listing,
            'seller': seller,
        })

    elif seller_id:
        seller = get_object_or_404(User, id=seller_id)

        if request.user == seller:
            messages.error(request, "You cannot review yourself.")
            return redirect('profile', pk=seller.id)

        listings = Listing.objects.filter(seller=seller)
        existing_review = Review.objects.filter(
            user=request.user,
            listing__seller=seller
        ).first()

        if request.method == 'POST':
            form = ReviewForm(request.POST, instance=existing_review)
            if form.is_valid():
                review = form.save(commit=False)
                review.user = request.user
                # Use the first listing or let user choose - you might want to improve this
                review.listing = listings.first()
                review.save()
                
                # Use review.listing instead of undefined 'listing' variable
                notify_new_review(seller, request.user, review, review.listing)
                
                messages.success(request, "Thank you for your review!")
                return redirect('profile', pk=seller.id)
        else:
            form = ReviewForm(instance=existing_review)

        return render(request, 'reviews/create_review.html', {
            'form': form,
            'seller': seller,
            'listings': listings,
        })
    else:
        messages.error(request, "No listing or seller specified for review.")
        return redirect('home')