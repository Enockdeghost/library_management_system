import flet as ft
import json
import os
from datetime import datetime

DATA_FILE = "stationery_data.json"

class StationeryItem:
    def __init__(self, name: str, quantity: int = 1, price: float = 0.0):
        self.name = name.strip()
        self.quantity = quantity
        self.price = price

    def to_dict(self): 
        return {"name": self.name, "quantity": self.quantity, "price": self.price}

    @staticmethod
    def from_dict(data):
        return StationeryItem(data["name"], data["quantity"], data["price"])


class ItemCard(ft.Container):
    def __init__(self, item: StationeryItem, on_update, on_delete, parent_page: ft.Page):
        super().__init__()
        self.item = item
        self.on_update = on_update
        self.on_delete = on_delete
        self._parent_page = parent_page

        self.name_text = ft.Text(item.name, size=16, weight=ft.FontWeight.W_500, expand=True)
        self.qty_text = ft.Text(str(item.quantity), size=14)
        self.price_text = ft.Text(f"${item.price:.2f}", size=14, color=ft.Colors.GREEN_700)
        self.total_text = ft.Text(f"${item.quantity * item.price:.2f}", size=14, weight=ft.FontWeight.BOLD)

        self.qty_minus = ft.IconButton(icon=ft.Icons.REMOVE, icon_size=18, on_click=self.decrement_qty)
        self.qty_plus = ft.IconButton(icon=ft.Icons.ADD, icon_size=18, on_click=self.increment_qty)
        self.edit_btn = ft.IconButton(icon=ft.Icons.EDIT, icon_color=ft.Colors.BLUE_600, on_click=self.edit_item)
        self.delete_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, on_click=self.delete_item)

        self.content = ft.Column(
            controls=[
                ft.Row(
                    controls=[self.name_text, ft.Row(controls=[self.edit_btn, self.delete_btn], spacing=0)],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Row(
                    controls=[
                        ft.Text("Qty:", size=12, color=ft.Colors.GREY_600),
                        self.qty_minus, self.qty_text, self.qty_plus,
                        ft.VerticalDivider(width=1),
                        ft.Text("Price:", size=12, color=ft.Colors.GREY_600), self.price_text,
                        ft.VerticalDivider(width=1),
                        ft.Text("Total:", size=12, color=ft.Colors.GREY_600), self.total_text,
                    ],
                    spacing=8,
                ),
            ],
            spacing=8,
        )

        super().__init__(
            content=self.content,
            bgcolor=ft.Colors.WHITE,
            padding=12,
            border_radius=10,
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=4, color=ft.Colors.BLACK12),
            margin=ft.margin.only(bottom=8),
        )

    def refresh_display(self):
        self.qty_text.value = str(self.item.quantity)
        self.price_text.value = f"${self.item.price:.2f}"
        self.total_text.value = f"${self.item.quantity * self.item.price:.2f}"
        self.update()

    def increment_qty(self, e):
        self.item.quantity += 1
        self.refresh_display()
        self.on_update()

    def decrement_qty(self, e):
        if self.item.quantity > 1:
            self.item.quantity -= 1
            self.refresh_display()
            self.on_update()
        else:
            self.delete_item(e)

    def edit_item(self, e):
        name_field = ft.TextField(label="Item Name", value=self.item.name)
        price_field = ft.TextField(label="Price ($)", value=str(self.item.price), keyboard_type=ft.KeyboardType.NUMBER)

        def save_changes(e):
            new_name = name_field.value.strip()
            if new_name:
                self.item.name = new_name
                self.name_text.value = new_name
            try:
                new_price = float(price_field.value)
                if new_price >= 0:
                    self.item.price = new_price
            except ValueError:
                pass
            self.refresh_display()
            self.on_update()
            dialog.open = False
            self._parent_page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Edit Item"),
            content=ft.Column([name_field, price_field], tight=True, spacing=10),
            actions=[ft.TextButton("Cancel", on_click=lambda e: setattr(dialog, 'open', False)),
                     ft.ElevatedButton("Save", on_click=save_changes)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._parent_page.dialog = dialog
        dialog.open = True
        self._parent_page.update()

    def delete_item(self, e):
        def confirm_delete(e):
            self.on_delete(self)
            dialog.open = False
            self._parent_page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Delete Item"),
            content=ft.Text(f"Are you sure you want to delete '{self.item.name}'?"),
            actions=[ft.TextButton("Cancel", on_click=lambda e: setattr(dialog, 'open', False)),
                     ft.ElevatedButton("Delete", on_click=confirm_delete, bgcolor=ft.Colors.RED_400)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._parent_page.dialog = dialog
        dialog.open = True
        self._parent_page.update()


class StationeryApp(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self._parent_page = page
        self.items = []
        self.cards = []
        self._initialized = False  # flag to prevent update before mount

        self.name_input = ft.TextField(hint_text="Item name", expand=True, border_radius=30, filled=True, on_submit=self.add_item)
        self.price_input = ft.TextField(hint_text="Price ($)", width=120, border_radius=30, filled=True, keyboard_type=ft.KeyboardType.NUMBER)
        self.add_button = ft.ElevatedButton("Add Item", icon=ft.Icons.ADD, bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE, on_click=self.add_item)
        self.search_field = ft.TextField(hint_text="Search", expand=True, border_radius=30, filled=True, on_change=self.filter_items)
        self.clear_search_btn = ft.IconButton(icon=ft.Icons.CLOSE, on_click=self.clear_search)
        self.stats_text = ft.Text("Total items: 0 | Total value: $0.00", size=14, color=ft.Colors.GREY_700)
        self.items_column = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO, expand=True)
        self.clear_all_btn = ft.OutlinedButton("Clear All", icon=ft.Icons.DELETE_SWEEP, on_click=self.clear_all, style=ft.ButtonStyle(color=ft.Colors.RED_400))
        self.export_btn = ft.OutlinedButton("Export CSV", icon=ft.Icons.SAVE_ALT, on_click=self.export_csv)

        main_column = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row([ft.Icon(ft.Icons.STORE, size=40, color=ft.Colors.BLUE_700),
                                    ft.Text("Uptown Stationery Manager", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                                    ft.Icon(ft.Icons.SHOPPING_BAG, size=40, color=ft.Colors.BLUE_700)],
                                   alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                    margin=ft.margin.only(bottom=20),
                ),
                ft.Row([self.name_input, self.price_input, self.add_button], spacing=10),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.Row([self.search_field, self.clear_search_btn], spacing=5),
                ft.Row([self.stats_text], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(height=10),
                ft.Text("Your Stationery Inventory:", size=18, weight=ft.FontWeight.W_500),
                self.items_column,
                ft.Row([self.clear_all_btn, self.export_btn], alignment=ft.MainAxisAlignment.END, spacing=10),
            ],
            spacing=12,
            expand=True,
        )

        self.content = main_column
        self.bgcolor = ft.Colors.GREY_50
        self.padding = 30
        self.border_radius = 20
        self.shadow = ft.BoxShadow(spread_radius=1, blur_radius=15, color=ft.Colors.BLACK12)
        self.expand = True

        # Do not load data or refresh here – wait for did_mount

    def did_mount(self):
        """Called after the control is added to the page."""
        self._initialized = True
        self.load_data()
        self.refresh_items_list()

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump([item.to_dict() for item in self.items], f, indent=2)

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    self.items = [StationeryItem.from_dict(d) for d in json.load(f)]
            except:
                self.items = []

    def refresh_items_list(self, filter_text=""):
        self.cards.clear()
        self.items_column.controls.clear()
        filtered = [i for i in self.items if filter_text.lower() in i.name.lower()] if filter_text else self.items
        for item in filtered:
            self.cards.append(ItemCard(item, self.on_item_update, self.delete_item_card, self._parent_page))
            self.items_column.controls.append(self.cards[-1])
        total_qty = sum(i.quantity for i in self.items)
        total_val = sum(i.quantity * i.price for i in self.items)
        self.stats_text.value = f"Total items: {total_qty} | Total value: ${total_val:.2f}"
        if self._initialized:
            self.update()

    def on_item_update(self):
        self.save_data()
        self.refresh_items_list(self.search_field.value)

    def delete_item_card(self, card):
        if card.item in self.items:
            self.items.remove(card.item)
            self.save_data()
            self.refresh_items_list(self.search_field.value)

    def add_item(self, e):
        name = self.name_input.value.strip()
        price_str = self.price_input.value.strip()
        if not name:
            self.name_input.error_text = "Name required"
            self.name_input.update()
            return
        self.name_input.error_text = None
        try:
            price = float(price_str) if price_str else 0.0
        except:
            price = 0.0

        for existing in self.items:
            if existing.name.lower() == name.lower():
                existing.quantity += 1
                self.save_data()
                self.refresh_items_list(self.search_field.value)
                self.name_input.value = ""
                self.price_input.value = ""
                self.name_input.focus()
                return

        self.items.append(StationeryItem(name, 1, price))
        self.save_data()
        self.refresh_items_list(self.search_field.value)
        self.name_input.value = ""
        self.price_input.value = ""
        self.name_input.focus()

    def filter_items(self, e):
        self.refresh_items_list(self.search_field.value)

    def clear_search(self, e):
        self.search_field.value = ""
        self.refresh_items_list("")

    def clear_all(self, e):
        if not self.items:
            return
        def confirm(e):
            self.items.clear()
            self.save_data()
            self.refresh_items_list("")
            dialog.open = False
            self.update()
        dialog = ft.AlertDialog(
            title=ft.Text("Clear All"),
            content=ft.Text("Delete ALL items? Cannot undo."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: setattr(dialog, 'open', False)),
                     ft.ElevatedButton("Yes", on_click=confirm, bgcolor=ft.Colors.RED_400)],
        )
        self._parent_page.dialog = dialog
        dialog.open = True
        self._parent_page.update()

    def export_csv(self, e):
        if not self.items:
            self._parent_page.snack_bar = ft.SnackBar(ft.Text("No items to export"), bgcolor=ft.Colors.ORANGE_400)
            self._parent_page.snack_bar.open = True
            self._parent_page.update()
            return
        filename = f"stationery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, "w") as f:
            f.write("Name,Quantity,Price,Total\n")
            for item in self.items:
                f.write(f'"{item.name}",{item.quantity},{item.price:.2f},{item.quantity * item.price:.2f}\n')
        self._parent_page.snack_bar = ft.SnackBar(ft.Text(f"Exported to {filename}"), bgcolor=ft.Colors.GREEN_400)
        self._parent_page.snack_bar.open = True
        self._parent_page.update()


def main(page: ft.Page):
    page.title = "Uptown Stationery Manager"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.bgcolor = ft.Colors.BLUE_50
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.window_width = 800
    page.window_height = 700
    page.window_min_width = 600
    page.window_min_height = 500
    page.add(StationeryApp(page))

ft.app(target=main)