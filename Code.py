from oandapyV20 import API
from oandapyV20.exceptions import V20Error
from oandapyV20.endpoints.instruments import InstrumentsCandles
from datetime import datetime, timedelta
import pandas as pd
from oandapyV20.endpoints.pricing import PricingInfo
import time
import nest_asyncio
import asyncio
from telegram import Bot


access_token = 'Yours'
accountID = 'Yours'
api = API(access_token=access_token)

# Telegram bot token and chat ID
telegram_bot_token = 'Yours'
telegram_chat_id = 'Yours'

bot = Bot(token=telegram_bot_token)

async def send_telegram_message(pair, closing_price, price_levels, message):
    try:
        full_message = f"Alert: Pair {pair} has a condition met in the current iteration!\n"
        full_message += f"Closing Price: {closing_price}\n"
        full_message += f"Price Levels: {price_levels}\n"
        full_message += f"Message: {message}"

        await bot.send_message(chat_id=telegram_chat_id, text=full_message)
        print("Telegram message sent successfully!")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def calculate_atr_levels(pair, closing_price, daily_movement, pair_multipliers):
    pair_multipliers = {"AUD_JPY": 100, "EUR_JPY": 100, "GBP_JPY": 100, "USD_JPY": 100, "CHF_JPY": 100, "NZD_JPY": 100, "WTICO_USD": 100}
    default_multiplier = 10000
    pair_multiplier = pair_multipliers.get(pair, default_multiplier)
    atr_high = closing_price + (daily_movement / pair_multiplier)
    atr_low = closing_price - (daily_movement / pair_multiplier)
    return atr_low, atr_high

def get_closing_price(pair):
    end_time = datetime.utcnow()  # Use UTC time
    start_time = end_time - timedelta(days=10)

    params = {
        "granularity": "H1",
        "from": start_time.isoformat() + "Z",
        "to": end_time.isoformat() + "Z",
        "price": "M",
    }

    try:
        request = InstrumentsCandles(instrument=pair, params=params)
        response = api.request(request)
        candles = response.get('candles', [])

        if candles:
            for candle in reversed(candles):
                time_utc = datetime.strptime(candle['time'][:19], '%Y-%m-%dT%H:%M:%S')
                time_montreal = time_utc - timedelta(hours=5)
                if time_montreal.hour == 17:
                    closing_price = float(candle['mid']['c'])
                    return closing_price, time_montreal

    except V20Error as e:
        print(f"Error: {e}")

    return None, None

# Function to process user input and calculate ATR levels for each pair
def process_user_input(user_input, pair_multipliers):
    data_list = []

    triplets = user_input.replace('\t', ' ').split()

    if len(triplets) % 3 != 0:
        print("Invalid input. Please provide pair, closing price, and daily movement for each entry.")
        return data_list

    for i in range(0, len(triplets), 3):
        data_parts = triplets[i:i+3]
        pair = data_parts[0].replace("/", "_")
        daily_movement = float(data_parts[1])
        closing_price, closing_time = get_closing_price(pair)

        if closing_price is not None and closing_time is not None:
            atr_low, atr_high = calculate_atr_levels(pair, closing_price, daily_movement, pair_multipliers)
            level_data = {
                'Pair': pair,
                'Closing_Price': closing_price,
                'Closing_Time': closing_time,
                'ATR_Low': atr_low,
                'ATR_High': atr_high
            }
            data_list.append(level_data)

    return data_list

# Function to input Forex data from the user
def input_forex_data():
    data_list = []

    print("Enter the data for the Forex pair, timeframe, and price levels (or type 'done' to finish):")
    while True:
        input_data = input("Enter data (e.g., GBP_USD H1 1.3000 1.3100 1.3200): ")

        if input_data.lower() == 'done':
            break

        data_parts = input_data.split()

        if len(data_parts) < 3:
            print("Invalid input. Please provide at least pair, timeframe, and one price level.")
            continue

        pair = data_parts[0]
        timeframe = data_parts[1]
        price_levels = ','.join(data_parts[2:])

        level_data = {
            'Pair': pair,
            'Timeframe': timeframe,
            'PriceLevels': price_levels,
        }

        data_list.append(level_data)
        print(f"Data entered successfully: {level_data}")

    # Convert 'PriceLevels' to a list of floats
    for data in data_list:
        data['PriceLevels'] = [float(level) for level in str(data['PriceLevels']).split(',') if level.strip()]

    # Convert the list of dictionaries to a Pandas DataFrame
    df = pd.DataFrame(data_list)
    print("DataFrame created successfully:")
    print(df)

    return df

# Example usage:
user_input = input("Enter the data for the Forex pairs and daily movements (separated by tabs or spaces, e.g., 'AUD/CAD 68.13 0.78 AUD/CHF 49.75 0.88 AUD/JPY 87.02 0.91'):\n")
pair_multipliers = {"AUD_JPY": 100, "EUR_JPY": 100, "GBP_JPY": 100, "USD_JPY": 100, "CHF_JPY": 100, "NZD_JPY": 100, "WTICO_USD": 100}

result = process_user_input(user_input, pair_multipliers) #ATR
ATR_DF = pd.DataFrame(result)#ATR

user_input_df = input_forex_data() #levels
print("User Input DataFrame:")
print(user_input_df)

# Merge the DataFrames on the 'Pair' column
merged_df = pd.merge(user_input_df, ATR_DF, on='Pair', how='left')

print(merged_df)

pair_multipliers_diff = {"AUD_JPY": 100, "EUR_JPY": 100, "GBP_JPY": 100, "USD_JPY": 100, "CHF_JPY": 100, "NZD_JPY": 100, "WTICO_USD": 100}

# Add new columns 'ATR_High_Diff' and 'ATR_Low_Diff' to merged_df
merged_df['ATR_High_Diff'] = None
merged_df['ATR_Low_Diff'] = None

for index, row in merged_df.iterrows():
    price_levels = row['PriceLevels']

    if isinstance(price_levels, list):
        atr_high_diff = [(row['ATR_High'] - level) * pair_multipliers_diff.get(row['Pair'], 10000) for level in price_levels]
        atr_low_diff = [(row['ATR_Low'] - level) * pair_multipliers_diff.get(row['Pair'], 10000) for level in price_levels]
    else:
        atr_high_diff = (row['ATR_High'] - price_levels) * pair_multipliers_diff.get(row['Pair'], 10000)
        atr_low_diff = (row['ATR_Low'] - price_levels) * pair_multipliers_diff.get(row['Pair'], 10000)

    merged_df.at[index, 'ATR_High_Diff'] = atr_high_diff
    merged_df.at[index, 'ATR_Low_Diff'] = atr_low_diff
    
# Add new column 'LEVEL_TYPE' to merged_df
merged_df['LEVEL_TYPE'] = None

# Example pair-specific multipliers (you can customize this)
pair_multipliers_level = {"AUD_JPY": 100, "EUR_JPY": 100, "GBP_JPY": 100, "USD_JPY": 100, "CHF_JPY": 100, "NZD_JPY": 100, "WTICO_USD": 100}

for index, row in merged_df.iterrows():
    price_levels = row['PriceLevels']
    atr_low = row['ATR_Low']
    atr_high = row['ATR_High']
    atr_low_diff = row['ATR_Low_Diff']
    atr_high_diff = row['ATR_High_Diff']

    if isinstance(price_levels, list):
        level_types = []
        for level in price_levels:
            diff_to_low = abs(level - atr_low) * pair_multipliers_level.get(row['Pair'], 10000)
            diff_to_high = abs(level - atr_high) * pair_multipliers_level.get(row['Pair'], 10000)

            if level < atr_low and diff_to_low <= 10:
                level_types.append("Level on ATR_LOW") 
            elif level < atr_low and diff_to_low > 10:
                level_types.append("Outside ATR")
            elif level > atr_high and diff_to_high <= 10:
                level_types.append("Level on ATR_HIGH")
            elif level > atr_high and diff_to_high > 10:
                level_types.append("Outside ATR_LEVELS")
            elif atr_low < level < atr_high and diff_to_low < 10:
                level_types.append("Level on ATR_LOW")
            elif atr_low < level < atr_high and diff_to_high < 10:
                level_types.append("Level on ATR_HIGH")
            else:
                level_types.append("Inside ATR LEVELS")
        merged_df.at[index, 'LEVEL_TYPE'] = level_types
    else:
        # Single level case
        diff_to_low = abs(price_levels - atr_low) * pair_multipliers_level.get(row['Pair'], 10000)
        diff_to_high = abs(price_levels - atr_high) * pair_multipliers_level.get(row['Pair'], 10000)

        level_types = []
        if level < atr_low and diff_to_low <= 10:
            level_types.append("Level on ATR_LOW") 
        elif level < atr_low and diff_to_low > 10:
            level_types.append("Outside ATR")
        elif level > atr_high and diff_to_high <= 10:
            level_types.append("Level on ATR_HIGH")
        elif level > atr_high and diff_to_high > 10:
            level_types.append("Outside ATR_LEVELS")
        elif atr_low < level < atr_high and diff_to_low < 10:
            level_types.append("Level on ATR_LOW")
        elif atr_low < level < atr_high and diff_to_high < 10:
            level_types.append("Level on ATR_HIGH")
        else:
            level_types.append("Inside ATR LEVELS")
        merged_df.at[index, 'LEVEL_TYPE'] = level_types

# Print the updated DataFrame
print(merged_df)

# List to store results for each iteration
result_list = []
# Create the Telegram bot instance

# Counter variable to keep track of the iteration number
iteration_counter = 1

async def main():
    global iteration_counter  # Declare iteration_counter as a global variable
    iteration_counter = 1

    try:
        while True:
            # Print the iteration number at the beginning of each iteration
            print(f"Iteration {iteration_counter}")

            # Create a new DataFrame for each iteration
            price_data = pd.DataFrame(columns=["Pair", "avg_price"])

            # Get pricing data for pairs in merged_df
            data = []

            for index, row in merged_df.iterrows():
                currency_pair = row['Pair']
                response = api.request(PricingInfo(accountID, params={"instruments": currency_pair}))
                bid_price = response["prices"][0]["bids"][0]["price"]
                ask_price = response["prices"][0]["asks"][0]["price"]
                avg_price = (float(bid_price) + float(ask_price)) / 2.0
                
                data.append({
                    "Pair": currency_pair,
                    "avg_price": avg_price
                })

            # Append prices to the DataFrame
            price_data = pd.DataFrame(data)  # This line creates a new DataFrame

            # Merge price_data with merged_df
            merged_result = pd.merge(price_data, merged_df, on='Pair', how='outer')
            merged_result = merged_result.drop(['Closing_Time'], axis=1)

            # Define a dictionary with pair-specific multipliers
            pair_specific_multipliers = {"AUD_JPY": 100, "EUR_JPY": 100, "GBP_JPY": 100, "USD_JPY": 100, "CHF_JPY": 100, "NZD_JPY": 100, "WTICO_USD": 100}

            # Calculate the absolute difference between avg_price and PriceLevels, multiplied by the pair-specific multiplier
            merged_result['Price_to_Level_in_Pips'] = merged_result.apply(lambda row: [abs(row['avg_price'] - level) * pair_specific_multipliers.get(row['Pair'], 10000) for level in row['PriceLevels']], axis=1)
            # Add a new column 'Alert' as a list based on the conditions
            merged_result['Alert'] = merged_result.apply(lambda row: ['Yes' if (
                (level_type == "Outside ATR_LEVELS" or level_type == "Level on ATR_LOW" or level_type == "Level on ATR_HIGH") 
                and pips <= 15
            ) else 'No' for level_type, pips in zip(row['LEVEL_TYPE'], row['Price_to_Level_in_Pips'])], axis=1)

            # Iterate through each row and check for 'Yes' in the 'Alert' list
            for index, row in merged_result.iterrows():
                for alert in row['Alert']:
                    if alert == 'Yes':
                        # Pass the necessary arguments to the function
                        await send_telegram_message(row['Pair'], row['Closing_Price'], row['PriceLevels'], "your_message_here")
            # Print the DataFrame at each iteration
            print(merged_result)

            # Print a message for each iteration
            print("Data collected and merged successfully.")

						# Increment the iteration counter
            iteration_counter += 1

            # Wait for 5 minutes
            await asyncio.sleep(300)  # 5 minutes (300 seconds)

    except KeyboardInterrupt:
        print("Script interrupted by the user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print("Script completed.")

if __name__ == "__main__":
    # Use nest_asyncio to run the asyncio event loop in a script
    nest_asyncio.apply()
    asyncio.run(main())