"""FSM states for the shop bot."""

from aiogram.filters.state import State, StatesGroup


class AdminStates(StatesGroup):
    """Admin authentication states."""

    waiting_password = State()


class CategoryStates(StatesGroup):
    """Product category management states."""

    waiting_name = State()
    waiting_edit_name = State()
    waiting_edit_description = State()
    waiting_edit_emoji = State()
    waiting_edit_sort_order = State()


class ProductStates(StatesGroup):
    """Product creation/editing states."""

    # Creation
    waiting_title = State()
    waiting_description = State()
    waiting_price = State()
    waiting_stock = State()
    waiting_category = State()
    waiting_image = State()
    waiting_unlimited_stock = State()

    # Editing
    editing_select_field = State()
    waiting_edit_title = State()
    waiting_edit_description = State()
    waiting_edit_price = State()
    waiting_edit_stock = State()
    waiting_edit_image = State()
    waiting_edit_unlimited_stock = State()

    # Moving
    waiting_move_category = State()


class ConfigProductStates(StatesGroup):
    """Config product creation/editing states."""

    waiting_title = State()
    waiting_description = State()
    waiting_price = State()
    waiting_stock = State()
    waiting_category = State()
    waiting_image = State()

    editing_select_field = State()
    waiting_edit_title = State()
    waiting_edit_description = State()
    waiting_edit_price = State()
    waiting_edit_stock = State()
    waiting_edit_image = State()


class CustomStates(StatesGroup):
    """Custom tournament creation/editing states."""

    waiting_title = State()
    waiting_description = State()
    waiting_rules = State()
    waiting_date = State()
    waiting_time = State()
    waiting_prize = State()
    waiting_entry_fee = State()
    waiting_capacity = State()
    waiting_category = State()
    waiting_banner = State()

    editing_select_field = State()
    waiting_edit_title = State()
    waiting_edit_description = State()
    waiting_edit_rules = State()
    waiting_edit_date = State()
    waiting_edit_time = State()
    waiting_edit_prize = State()
    waiting_edit_entry_fee = State()
    waiting_edit_capacity = State()

    waiting_cancel_reason = State()
    waiting_notify_message = State()

    # Winner selection
    waiting_winner_type = State()
    waiting_winner_team_name = State()
    waiting_winner_username = State()

    # Prize management (new)
    waiting_prize_content = State()  # Admin sends prize (text/photo/video/document)
    waiting_prize_confirmation = State()  # Confirm prize before saving

    # Start message management (new)
    waiting_start_message = State()  # Admin enters start message
    waiting_start_message_confirmation = State()  # Confirm start message

    # Postpone management (new)
    waiting_postpone_date = State()  # Admin enters new date
    waiting_postpone_time = State()  # Admin enters new time

    # Start custom confirmation (new)
    waiting_start_confirmation = State()  # Confirm start when no start message


class CustomCategoryStates(StatesGroup):
    """Custom category management states."""

    waiting_name = State()
    waiting_edit_name = State()


class AdminCustomCategoryStates(StatesGroup):
    """Admin custom category management states."""

    waiting_name = State()
    waiting_emoji = State()
    waiting_edit_name = State()
    waiting_edit_emoji = State()


class AdminBackupStates(StatesGroup):
    """Admin backup management states."""

    waiting_backup_file = State()


class TicketStates(StatesGroup):
    """Support ticket states."""

    waiting_category = State()  # Actually selecting via callback
    choosing_category = State()
    waiting_message = State()
    waiting_subject = State()
    reply_to_ticket = State()  # admin replying
    waiting_admin_reply = State()
    waiting_close_reason = State()


class AccountInfoStates(StatesGroup):
    """Product account info collection states."""

    waiting_codm_username = State()
    waiting_email = State()
    waiting_password = State()
    waiting_confirmation = State()


class CustomRegistrationStates(StatesGroup):
    """Custom registration flow states."""

    waiting_codm_username = State()
    waiting_confirmation = State()


class SettingsStates(StatesGroup):
    """Settings management states."""

    waiting_card_number = State()
    waiting_card_holder = State()
    waiting_bank_name = State()
    waiting_support_text = State()
    waiting_welcome_message = State()
    waiting_admin_ids = State()
    waiting_value = State()       # generic text/integer value for a setting
    waiting_media = State()       # photo upload for a media setting
    waiting_button_value = State()  # button label text


class BroadcastStates(StatesGroup):
    """Smart broadcast composer + legacy states."""

    waiting_message = State()
    waiting_photo = State()
    waiting_video = State()
    waiting_file = State()

    # New smart-broadcast states
    waiting_title = State()
    waiting_text = State()
    waiting_media = State()
    waiting_caption = State()
    waiting_poll_question = State()
    waiting_poll_options = State()
    waiting_buttons = State()
    waiting_schedule = State()
    waiting_interval = State()
    waiting_template_name = State()


class SearchStates(StatesGroup):
    """Search states."""

    waiting_user_query = State()
    waiting_ticket_query = State()
    waiting_product_query = State()


class AdminRolesStates(StatesGroup):
    """Admin roles management FSM."""

    waiting_admin_telegram_id = State()  # telegram id to promote
    waiting_role_pick = State()          # pick a role for the new/edited admin
    waiting_suspend_reason = State()     # reason for suspending/removing
    waiting_permission_toggle = State()  # (set by callback, not text)


class FinancialStates(StatesGroup):
    """Financial dashboard filter states."""

    waiting_date_from = State()
    waiting_date_to = State()
    waiting_user = State()
    waiting_product = State()
    waiting_category = State()
    waiting_payment_status = State()
    waiting_admin = State()


class AbusePanelStates(StatesGroup):
    """Admin anti-abuse panel states."""

    waiting_tg_id = State()
    waiting_black_reason = State()
    waiting_ban_reason = State()
    waiting_mute_hours = State()


class DashboardStates(StatesGroup):
    """User dashboard / profile edit states."""

    edit_first_name = State()
    edit_last_name = State()


class PaymentStates(StatesGroup):
    """Payment receipt collection states."""

    waiting_receipt = State()  # user uploads receipt image
    waiting_custom_receipt = State()  # custom registration receipt


class CustomCartStates(StatesGroup):
    """Custom cart registration flow."""

    waiting_codm_username = State()
    waiting_confirmation = State()
    waiting_payment_receipt = State()


class AdminOrderStates(StatesGroup):
    """Admin order management FSM."""

    waiting_note = State()            # internal note text
    waiting_customer_note = State()   # customer note
    waiting_reject_reason = State()   # rejection reason
    waiting_cancel_reason = State()   # cancellation reason
    waiting_eta = State()             # estimated delivery datetime
    waiting_filter_number = State()   # filter by order number
    waiting_filter_user = State()     # filter by user (search)
    waiting_filter_price = State()    # filter by price range "min-max"
    waiting_filter_date = State()     # filter by date range "from-to"
    waiting_ticket_link = State()     # enter ticket id to link
    waiting_search_number = State()   # direct order-number lookup
    waiting_delivery_data = State()   # delivered account info

    # Filter pickers (no text input)
    pick_status = State()
    pick_payment_status = State()


class TopUpStates(StatesGroup):
    """Wallet top-up flow (user side)."""

    waiting_custom_amount = State()   # user types a custom amount
    waiting_receipt = State()         # user sends receipt image
    resubmit_receipt = State()        # user resubmits receipt after rejection


class AdminTopUpStates(StatesGroup):
    """Admin top-up management FSM."""

    waiting_search_code = State()     # search by tracking code
    waiting_reject_reason = State()   # reject reason text

    # Manual credit/debit
    waiting_credit_user = State()     # telegram id or pick user
    waiting_credit_amount = State()   # amount to credit
    waiting_credit_note = State()     # optional note
    waiting_debit_user = State()      # telegram id or pick user
    waiting_debit_amount = State()    # amount to debit
    waiting_debit_reason = State()    # required reason

    # Top-up amount management
    waiting_amount_value = State()    # new/edit amount value
    waiting_amount_label = State()    # optional label

class AdminTicketCategoryStates(StatesGroup):
    """Admin ticket category management FSM."""
    
    waiting_name = State()            # category name
    waiting_emoji = State()           # category emoji
    waiting_edit_name = State()       # edit category name
    waiting_edit_emoji = State()      # edit category emoji


class CustomerInfoStates(StatesGroup):
    """Customer info collection FSM."""
    
    waiting_email = State()           # customer email
    waiting_password = State()        # customer password
    waiting_customer_name = State()   # customer name


class AdminDeliveryStates(StatesGroup):
    """Admin config delivery FSM."""

    waiting_config_text = State()     # config text input
    waiting_config_file = State()     # config file upload
    waiting_delivery_note = State()   # delivery note (optional)
