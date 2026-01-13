import datetime

class RiskManager:
    def __init__(self, initial_balance, daily_risk_limit=0.01, max_drawdown_limit=0.06):
        self.initial_balance = initial_balance
        self.daily_risk_limit = daily_risk_limit
        self.max_drawdown_limit = max_drawdown_limit
        
        # State Tracking
        self.daily_starting_balance = initial_balance
        self.current_day = None
        self.high_water_mark = initial_balance
        self.in_cooldown = False

    def check_trade_allowed(self, current_date, current_equity):
        # 1. NEW DAY RESET
        # If the date has changed, reset the "Daily Starting Balance"
        if self.current_day != current_date.date():
            self.current_day = current_date.date()
            self.daily_starting_balance = current_equity
            self.in_cooldown = False # Reset cooldown for new day

        # 2. CHECK DAILY LOSS (The "Daily Kill Switch")
        daily_loss_amount = self.daily_starting_balance - current_equity
        daily_loss_pct = daily_loss_amount / self.daily_starting_balance

        if daily_loss_pct >= self.daily_risk_limit:
            self.in_cooldown = True
            return False, f"🛑 DAILY LIMIT HIT: Down {daily_loss_pct*100:.2f}% today."

        # 3. CHECK MAX DRAWDOWN (The "Prop Firm" Limit)
        if current_equity > self.high_water_mark:
            self.high_water_mark = current_equity
        
        total_drawdown_amount = self.high_water_mark - current_equity
        total_drawdown_pct = total_drawdown_amount / self.high_water_mark

        if total_drawdown_pct >= self.max_drawdown_limit:
            return False, f"❌ ACCOUNT BLOWN: Max Drawdown {total_drawdown_pct*100:.2f}% hit."

        return True, "✅ Risk OK"