# listings/models.py
import os
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db.models import Avg

User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Bootstrap icon class name")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"

class Listing(models.Model):
    # Pre-defined list of Homabay locations
    HOMABAY_LOCATIONS = [
        ('HB_Town', 'Homa Bay Town'),
        ('Kendu_Bay', 'Kendu Bay'),
        ('Rodi_Kopany', 'Rodi Kopany'),
        ('Mbita', 'Mbita'),
        ('Oyugis', 'Oyugis'),
        ('Rangwe', 'Rangwe'),
        ('Ndhiwa', 'Ndhiwa'),
        ('Suba', 'Suba'),
    ]

    CONDITION_CHOICES = [
        ('new', 'New'),
        ('used', 'Used'),
        ('refurbished', 'Refurbished'),
    ]

    DELIVERY_OPTIONS = [
        ('pickup', 'Pickup'),
        ('delivery', 'Delivery'),
        ('shipping', 'Shipping'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    location = models.CharField(max_length=50, choices=HOMABAY_LOCATIONS)
    image = models.ImageField(upload_to='listing_images/', default='listing_images/default.png')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='used')
    delivery_option = models.CharField(max_length=20, choices=DELIVERY_OPTIONS, default='pickup')
    stock = models.PositiveIntegerField(default=1)
    is_sold = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings', null=True)
    

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('listing-detail', kwargs={'pk': self.pk})

    def get_condition_display(self):
        return dict(self.CONDITION_CHOICES).get(self.condition, 'Unknown')

    def get_delivery_option_display(self):
        return dict(self.DELIVERY_OPTIONS).get(self.delivery_option, 'Unknown')


    @property
    def average_rating(self):
        if self.reviews.count() > 0:
            return self.reviews.aggregate(Avg('rating'))['rating__avg']
        return 0
    
    def save(self, *args, **kwargs):
        # Ensure the directory exists before saving
        if self.image:
            # Create directory if it doesn't exist
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'listing_images'), exist_ok=True)
        super().save(*args, **kwargs)


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='favorites'
    )
    listing = models.ForeignKey(
        'Listing', 
        on_delete=models.CASCADE, 
        related_name='favorites'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'listing')
        ordering = ['-created_at']
        
class Activity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
# In your listings/models.py file, add these models
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart ({self.user.username})"

    def get_total_price(self):
        return sum(item.get_total_price() for item in self.items.all())

    @property
    def total_items(self):
        return self.items.count()


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'listing')

    def __str__(self):
        return f"{self.quantity} x {self.listing.title}"

    def get_total_price(self):
        return self.quantity * self.listing.price


class Order(models.Model):
    ORDER_STATUS = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('disputed', 'Disputed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    items = models.ManyToManyField(Listing, through='OrderItem')
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"

    def mark_as_paid(self):
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.save()
        
        # Mark all items as sold
        for order_item in self.order_items.all():
            order_item.listing.is_sold = True
            order_item.listing.save()


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.listing.title}"

    def get_total_price(self):
        return self.quantity * self.price


class Payment(models.Model):
    PAYMENT_METHODS = [
        ('mpesa', 'M-Pesa'),
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash on Delivery'),
    ]

    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='mpesa')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment for Order #{self.order.id}"

    def mark_as_completed(self, transaction_id):
        self.status = 'completed'
        self.transaction_id = transaction_id
        self.completed_at = timezone.now()
        self.save()
        
        # Mark order as paid
        self.order.mark_as_paid()


class Escrow(models.Model):
    ESCROW_STATUS = [
        ('held', 'Funds Held'),
        ('released', 'Funds Released to Seller'),
        ('refunded', 'Funds Refunded to Buyer'),
        ('disputed', 'Disputed'),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='escrow'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=ESCROW_STATUS, default='held')
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Escrow for Order #{self.order.id}"

    def release_funds(self):
        self.status = 'released'
        self.released_at = timezone.now()
        self.save()
        
        # In a real implementation, you would transfer funds to seller here
        # For now, we'll just update the status
        
        # Create activity log
        Activity.objects.create(
            user=self.order.user,
            action=f"Escrow released for Order #{self.order.id}"
        )

    def refund_funds(self):
        self.status = 'refunded'
        self.released_at = timezone.now()
        self.save()
        
        # In a real implementation, you would refund funds to buyer here
        
        # Create activity log
        Activity.objects.create(
            user=self.order.user,
            action=f"Escrow refunded for Order #{self.order.id}"
        )

class Review(models.Model):
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('listing', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"Review by {self.user.username} for {self.listing.title}"