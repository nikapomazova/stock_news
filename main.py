import pandas_market_calendars as mcal
import yfinance as yf
import pandas as pd
from datetime import date, datetime, timedelta
from pathlib import Path

# directions for cached data of tickers
DATA_DIR = Path("data")
MARKET_DATA_DIR = DATA_DIR / "market"
BETA_DATA_DIR = DATA_DIR / "beta"

MARKET_DATA_DIR.mkdir(parents=True, exist_ok=True)
BETA_DATA_DIR.mkdir(parents=True, exist_ok=True)

# importing market calendar
nyse = mcal.get_calendar("NYSE")
TRADING_HOURS_PER_DAY = 6.5
TRADING_MINUTES_PER_DAY = TRADING_HOURS_PER_DAY * 60

# guidance revision functions

def guidance_revision(old_guid, new_guid):
    return (new_guid - old_guid) / old_guid

def guidance_range_revision(old_low, old_high, new_low, new_high):
    old_guid = (old_high + old_low)/2
    new_guid = (new_high + new_low)/2
    return guidance_revision(old_guid, new_guid)

# helper functions

# Find the latest timestamp available in market-price data
# that is at or before the target time.
def get_available_time(data, target_time):
    valid_times = data.index[data.index <= target_time]
    if len(valid_times) == 0:
        raise ValueError(
            f"No price data available at or before {target_time}"
        )
    return valid_times[-1]

# Find return percentage
def calculate_return(start_price, end_price):
    return (end_price / start_price) - 1

# Find a and b adjusted returns
def a_and_b_adjusted_return(company_return, market_return, beta, alpha):
    expected_return = alpha + beta * market_return
    return company_return - expected_return

# Find the time when the regular market can first react to an event.
def get_event_start_times(event_time, schedule, price_data):
    schedule = schedule.copy()
    event_date = event_time.normalize().tz_localize(None)
    schedule["market_open"] = schedule["market_open"].dt.tz_convert("America/New_York")
    schedule["market_close"] = schedule["market_close"].dt.tz_convert("America/New_York")
    
    reaction_start = None

    if event_date in schedule.index:
        day_schedule = schedule.loc[event_date]
        market_open = day_schedule["market_open"]
        market_close = day_schedule["market_close"]
        
        if market_open <= event_time < market_close:
            reaction_start = event_time
            # subtracting 1 microsecond so that it's strictly before the reaction start
            baseline_time = get_available_time(price_data,
                                               event_time - pd.Timedelta(microseconds=1))
            
            return baseline_time, reaction_start
        elif event_time < market_open:
            reaction_start = market_open
    else:
        reaction_start = None
    
    if reaction_start is None:
        future_sessions = schedule[schedule["market_open"] > event_time] 
        reaction_start = future_sessions.iloc[0]["market_open"]
    
    # subtracting 1 microsecond so that it's strictly before the reaction start
    baseline_time = get_available_time(
        price_data,
        reaction_start - pd.Timedelta(microseconds=1)
    )

    return baseline_time, reaction_start

# Add a number of trading minutes to a timestamp.
def add_trading_minutes(start_time, minutes, schedule):
    schedule = schedule.copy()

    schedule["market_open"] = schedule["market_open"].dt.tz_convert(
        "America/New_York"
    )

    schedule["market_close"] = schedule["market_close"].dt.tz_convert(
        "America/New_York"
    )

    current_time = start_time
    minutes_left = minutes

    while minutes_left > 0:
        # finding the day we're in on the schedule
        current_day = schedule[
            (schedule["market_open"] <= current_time) &
            (schedule["market_close"] > current_time)
        ]

        # if we are outside trading hours, so go to next market open
        if current_day.empty:
            next_days = schedule[
                schedule["market_open"] > current_time
            ]

            reaction_day = next_days.iloc[0]["market_open"]
            current_time = reaction_day
            continue
        
        market_close = current_day.iloc[0]["market_close"]
        minutes_until_close = (
            market_close - current_time
        ).total_seconds() / 60

        if minutes_left <= minutes_until_close:
            return current_time + pd.Timedelta(minutes=minutes_left)
        else:
            minutes_left -= minutes_until_close

            next_days = schedule[
                schedule["market_open"] > market_close
            ]

            reaction_day = next_days.iloc[0]["market_open"]
            current_time = reaction_day

# Get the timestamps at which we want to measure the stock's reaction to an event.
def get_target_times(reaction_start, schedule):

    schedule = schedule.copy()

    schedule["market_open"] = schedule["market_open"].dt.tz_convert(
        "America/New_York"
    )
    schedule["market_close"] = schedule["market_close"].dt.tz_convert(
        "America/New_York"
    )

    immediate = reaction_start
    one_hour = add_trading_minutes(reaction_start, 60, schedule)
    one_day = add_trading_minutes(reaction_start, TRADING_MINUTES_PER_DAY, schedule)
    three_days = add_trading_minutes(reaction_start, TRADING_MINUTES_PER_DAY * 3, schedule)

    return {"immediate": immediate,
            "1 hour": one_hour,
            "1 day": one_day,
            "3 days": three_days}

# Find the actual time we should get the price from and the price itself
def get_time_and_price_at_target(data, target_time, ticker, schedule):
    schedule = schedule.copy()

    schedule["market_close"] = schedule["market_close"].dt.tz_convert(
        "America/New_York"
    )

    if (schedule["market_close"] == target_time).any():
        valid_times = data.index[data.index < target_time]
        actual_time = valid_times[-1]

        price = data.loc[actual_time, ("Close", ticker)]
    else:
        valid_times = data.index[data.index >= target_time]
        actual_time = valid_times[0]
        
        price = data.loc[actual_time, ("Open", ticker)]
    
    return actual_time, price

# Find the baseline price and time
def get_baseline_time_and_price(data, event_time, reaction_start, ticker):

    if reaction_start == event_time:
        valid_times = data.index[data.index < event_time]
        baseline_time = valid_times[-1]

        baseline_price = data.loc[baseline_time, ("Open", ticker)]

    else:
        valid_times = data.index[data.index < reaction_start]
        baseline_time = valid_times[-1]

        baseline_price = data.loc[baseline_time, ("Close", ticker)]

    return baseline_time, baseline_price

# final function to return immediate, 1 hour, 1 day, 3 days return of a company
# after an event, as well as its beta and alpha adjusted returns

def returns_adjusted(event, beta_data, market_ticker, schedule, ticker_data, market_ticker_data):

    ticker = event["ticker"]
    # ALPHA AND BETA

    # taking close prices from each day
    close_prices = beta_data["Close"]
    # calculating daily return
    daily_returns = close_prices.pct_change()
    # dropping NaN's
    daily_returns = daily_returns.dropna()
    # calculations
    covariance = daily_returns[ticker].cov(daily_returns[market_ticker])
    market_variance = daily_returns[market_ticker].var()
    beta = covariance / market_variance
    alpha = daily_returns[ticker].mean() - beta * daily_returns[market_ticker].mean()

    # RETURNS

    event_time = pd.Timestamp(event["event_time"], tz="America/New_York")

    _, reaction_start = get_event_start_times(
        event_time,
        schedule,
        ticker_data
    )

    target_times = get_target_times(reaction_start, schedule)

    baseline_time, baseline_price = get_baseline_time_and_price(ticker_data, event_time, reaction_start, ticker)
    baseline_time_market, baseline_price_market = get_baseline_time_and_price(market_ticker_data, event_time, reaction_start, market_ticker)

    _, immediate_price = get_time_and_price_at_target(ticker_data, target_times["immediate"], ticker, schedule)
    _, one_hour_price = get_time_and_price_at_target(ticker_data, target_times["1 hour"], ticker, schedule)
    _, one_day_price = get_time_and_price_at_target(ticker_data, target_times["1 day"], ticker, schedule)
    _, three_days_price = get_time_and_price_at_target(ticker_data, target_times["3 days"], ticker, schedule)

    _, immediate_price_market = get_time_and_price_at_target(market_ticker_data, target_times["immediate"], market_ticker, schedule)
    _, one_hour_price_market = get_time_and_price_at_target(market_ticker_data, target_times["1 hour"], market_ticker, schedule)
    _, one_day_price_market = get_time_and_price_at_target(market_ticker_data, target_times["1 day"], market_ticker, schedule)
    _, three_days_price_market = get_time_and_price_at_target(market_ticker_data, target_times["3 days"], market_ticker, schedule)

    immediate_return = calculate_return(baseline_price, immediate_price)
    one_hour_return = calculate_return(baseline_price, one_hour_price)
    one_day_return = calculate_return(baseline_price, one_day_price)
    three_days_return = calculate_return(baseline_price, three_days_price)

    immediate_return_market = calculate_return(baseline_price_market, immediate_price_market)
    one_hour_return_market = calculate_return(baseline_price_market, one_hour_price_market)
    one_day_return_market = calculate_return(baseline_price_market, one_day_price_market)
    three_days_return_market = calculate_return(baseline_price_market, three_days_price_market)

    # a is 0 because it was calculated based on daily, not hourly data
    immediate_adjusted_return = a_and_b_adjusted_return(immediate_return, immediate_return_market, beta, 0)
    one_hour_adjusted_return = a_and_b_adjusted_return(one_hour_return, one_hour_return_market, beta, 0)
    one_day_adjusted_return = a_and_b_adjusted_return(one_day_return, one_day_return_market, beta, alpha)
    three_days_adjusted_return = a_and_b_adjusted_return(three_days_return, three_days_return_market, beta, 3 * alpha)

    return {
        "immediate return": immediate_return,
        "1 hour return": one_hour_return,
        "1 day return": one_day_return,
        "3 days return": three_days_return,

        "immediate adjusted return": immediate_adjusted_return,
        "1 hour adjusted return": one_hour_adjusted_return,
        "1 day adjusted return": one_day_adjusted_return,
        "3 days adjusted return": three_days_adjusted_return
    }

# functions for using

def get_beta_data(ticker1, ticker2, start, finish, interval="1d"):
    return yf.download(
        [ticker1, ticker2],
        start=start,
        end=finish,
        interval=interval)

def get_stock_data(ticker, event, interval="5m", days_before=3, days_after=10):
    event_time = pd.Timestamp(event["event_time"])

    start_date = (event_time.normalize() - pd.Timedelta(days=days_before))
    end_date = (event_time.normalize() + pd.Timedelta(days=days_after))

    filename = (
        f"{ticker}_{start_date.date()}_{end_date.date()}_{interval}.parquet"
    )

    filepath = MARKET_DATA_DIR / filename

    if filepath.exists():
        print(f"Loading {ticker} from cache")
        return pd.read_parquet(filepath)

    print(f"Downloading {ticker}")

    data = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        interval=interval
    )

    data.to_parquet(filepath)

    return data

def analyze_event(event, market_ticker = "SPY"):
    ticker = event["ticker"]

    event_time = pd.Timestamp(
        event["event_time"],
        tz="America/New_York"
    )
    beta_start = event_time - pd.Timedelta(days=180)

    beta_data = get_beta_data(ticker,
                              market_ticker,
                              beta_start,
                              event_time)
    
    nyse = mcal.get_calendar("NYSE")

    schedule = nyse.schedule(
        start_date=event_time.normalize(),
        end_date=event_time.normalize() + pd.Timedelta(days=10)
    )
    
    stock_data = get_stock_data(ticker, event)
    market_stock_data = get_stock_data(market_ticker, event)
    return returns_adjusted(event,
                            beta_data,
                            market_ticker,
                            schedule,
                            stock_data,
                            market_stock_data)