from aiogram.fsm.state import State, StatesGroup

class CheckoutStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_address = State()
    waiting_for_payment = State()
    waiting_for_confirm = State()

class SearchStates(StatesGroup):
    waiting_for_query = State()

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    
    # Mahsulot qo'shish
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_desc = State()
    waiting_for_price = State()
    waiting_for_image = State()
