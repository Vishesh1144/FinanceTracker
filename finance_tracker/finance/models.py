# models
from django.db import models
from django.contrib.auth.models import User
from datetime import date

class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item_name = models.CharField(max_length=100, default="Unknown Item")
    type = models.CharField(
        max_length=20,
        choices=[("Expense", "Expense"), ("Income", "Income")],
        default="Expense"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    category = models.CharField(max_length=50, default="General")
    date = models.DateField(default=date.today)

    def __str__(self):
        return f"{self.item_name} - {self.type} - {self.amount}"
