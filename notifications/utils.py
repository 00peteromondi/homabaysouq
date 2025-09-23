from django.contrib.auth import get_user_model
from .models import Notification, NotificationPreference

User = get_user_model()

def create_notification(recipient, notification_type, title, message, 
                       sender=None, related_object_id=None, 
                       related_content_type='', action_url='', action_text=''):
    """
    Utility function to create notifications
    """
    # Get or create notification preferences
    preferences, created = NotificationPreference.objects.get_or_create(user=recipient)
    
    # Check if user wants this type of notification
    push_enabled = getattr(preferences, f'push_{notification_type.split("_")[0]}', True)
    
    if push_enabled:
        notification = Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_id=related_object_id,
            related_content_type=related_content_type,
            action_url=action_url,
            action_text=action_text
        )
        return notification
    return None

def notify_new_message(recipient, sender, message_content, conversation_id):
    """Notify about new message"""
    return create_notification(
        recipient=recipient,
        sender=sender,
        notification_type='message',
        title=f"New message from {sender.username}",
        message=message_content[:100] + "..." if len(message_content) > 100 else message_content,
        related_object_id=conversation_id,
        related_content_type='conversation',
        action_url=f'/conversation/{conversation_id}/',
        action_text='View Conversation'
    )

def notify_new_order(seller, buyer, order):
    """Notify seller about new order"""
    return create_notification(
        recipient=seller,
        sender=buyer,
        notification_type='order_placed',
        title="New Order Received",
        message=f"{buyer.username} placed an order for your listing",
        related_object_id=order.id,
        related_content_type='order',
        action_url=f'/seller/orders/',
        action_text='View Order'
    )

def notify_order_shipped(buyer, seller, order):
    """Notify buyer about shipped order"""
    return create_notification(
        recipient=buyer,
        sender=seller,
        notification_type='order_shipped',
        title="Order Shipped",
        message=f"Your order #{order.id} has been shipped by {seller.username}",
        related_object_id=order.id,
        related_content_type='order',
        action_url=f'/order/{order.id}/',
        action_text='Track Order'
    )

def notify_order_delivered(seller, buyer, order):
    """Notify seller about delivered order"""
    return create_notification(
        recipient=seller,
        sender=buyer,
        notification_type='order_delivered',
        title="Order Delivered",
        message=f"Your order #{order.id} has been delivered to {buyer.username}",
        related_object_id=order.id,
        related_content_type='order',
        action_url=f'/seller/orders/',
        action_text='View Order'
    )

def notify_payment_received(seller, buyer, order):
    """Notify seller about payment"""
    return create_notification(
        recipient=seller,
        sender=buyer,
        notification_type='payment_received',
        title="Payment Received",
        message=f"Payment received for order #{order.id} from {buyer.username}",
        related_object_id=order.id,
        related_content_type='order',
        action_url=f'/seller/orders/',
        action_text='View Details'
    )

def notify_new_review(recipient, reviewer, review, listing=None):
    """Notify about new review"""
    if listing:
        title = f"New Review on {listing.title}"
        message = f"{reviewer.username} left a {review.rating}-star review"
    else:
        title = "New Seller Review"
        message = f"{reviewer.username} left you a {review.rating}-star review"
    
    return create_notification(
        recipient=recipient,
        sender=reviewer,
        notification_type='review_received',
        title=title,
        message=message,
        related_object_id=review.id,
        related_content_type='review',
        action_url=f'/profile/{recipient.id}/' if not listing else f'/listing/{listing.id}/',
        action_text='View Review'
    )

def notify_listing_favorited(seller, user, listing):
    """Notify seller about favorite"""
    return create_notification(
        recipient=seller,
        sender=user,
        notification_type='favorite',
        title="Listing Favorited",
        message=f"{user.username} added your listing '{listing.title}' to favorites",
        related_object_id=listing.id,
        related_content_type='listing',
        action_url=f'/listing/{listing.id}/',
        action_text='View Listing'
    )

def notify_system_message(recipient, title, message, action_url=''):
    """Send system notification"""
    return create_notification(
        recipient=recipient,
        notification_type='system',
        title=title,
        message=message,
        related_content_type='system',
        action_url=action_url,
        action_text='View Details'
    )