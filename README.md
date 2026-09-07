# Stock News Impact Analysis

A Python project that looks at how company-specific news affects stock prices over different time periods.

## What it does

The project measures stock returns after a news event and compares them with the broader market to get a better idea of how much of the movement may be related to the event itself.

## Current analysis

Right now, the project calculates:
- immediate reaction
- 1 hour
- 1 trading day
- 3 trading days

The returns are adjusted using market performance, alpha, and beta.

## Market timing

The project accounts for whether news comes out before, during, or after market hours, so the reaction starts at the correct trading time.

## Tools

Python, Pandas, yfinance, pandas_market_calendars, Jupyter Notebook.

## Status

In progress. I am planning to add more events and improving the way the results are compared and summarized.
