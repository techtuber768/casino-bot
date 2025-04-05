import discord
import random
import os
import json
import openpyxl
import signal
import asyncio
import pandas as pd
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True  # Enable members intent
bot = commands.Bot(command_prefix="/", intents=intents)

# File paths
BALANCES_FILE = "balances.json"
TRANSACTIONS_FILE = "transactions.json"
TRANSACTIONS_EXCEL = "transactions.xlsx"

# Load data from file
def load_data(file_path):
    try:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:  # Ensure file exists & has content
            with open(file_path, "r") as file:
                data = json.load(file)
                if isinstance(data, dict):  # Ensure the loaded data is a dictionary
                    return data
        print(f"⚠️ Warning: {file_path} is empty or invalid. Using default values.")
        return {}  # Return empty dictionary if the file is empty or corrupted
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"⚠️ Error loading {file_path}. Using default values.")
        return {}


# Save data to file
def save_data(file_path, data):
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


# Load environment variables from a .env file
load_dotenv()
BOT_KEY = os.getenv("BOT_TOKEN")

tree = bot.tree

# Maximum bet limit
MAX_BET = 10000  # Change this value to adjust the betting limit

# User balances and transactions
balances = load_data(BALANCES_FILE)  # Ensure it loads
transactions = load_data(TRANSACTIONS_FILE)  # Ensure it loads

# Log transactions for each user
def log_transaction(user_id, description):
    if user_id not in transactions:
        transactions[user_id] = []  # Ensure user has a transaction list

    transactions[user_id].append(description)  # Log the new transaction
    save_data(TRANSACTIONS_FILE, transactions)  # Save immediately


# Helper function to get balance
def get_balance(user_id):
    user_id_str = str(user_id)  # Ensure we are checking string keys
    return balances.get(user_id_str, 0)  # Fetch using string key


# Helper function to update balance
def update_balance(user_id, amount):
    user_id_str = str(user_id)  # Convert user ID to string for consistency
    balances[user_id_str] = get_balance(user_id_str) + amount


# Command to check balance
@tree.command(name="balance", description="Check your balance")
async def balance(interaction: discord.Interaction):
    bal = get_balance(interaction.user.id)
    embed = discord.Embed(title="💰 Balance Check 💰", description=f"You have **${bal}** Redmont Dollars!", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Admin command to adjust a specific user's balance
@tree.command(name="adjust_balance", description="Adjust a specific user's balance (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def adjust_balance(interaction: discord.Interaction, user: discord.User, action: str, amount: int):
    await interaction.response.defer()  # Ensure bot does not timeout
    
    if action.lower() not in ["increase", "decrease"]:
        await interaction.followup.send("❌ Invalid action! Use 'increase' or 'decrease'.", ephemeral=True)
        return
    
    if action.lower() == "increase":
        update_balance(user.id, amount)
        log_transaction(user.id, f"Admin increased balance by ${amount}")
    else:
        update_balance(user.id, -amount)
        log_transaction(user.id, f"Admin decreased balance by ${amount}")
    
    await interaction.followup.send(f"✅ {user.mention}'s balance has been {'increased' if action.lower() == 'increase' else 'decreased'} by **${amount}**.", ephemeral=True)




# Roll Dice game
@tree.command(name="roll_dice", description="Roll a dice against the bot. If both rolls match, you win 3x your bet!")
async def roll_dice(interaction: discord.Interaction, bet: int):
    if bet <= 0 or bet > MAX_BET:
        await interaction.response.send_message(f"❌ Invalid bet amount! Must be between 1 and ${MAX_BET}.", ephemeral=True)
        return
    
    user_balance = get_balance(interaction.user.id)
    if bet > user_balance:
        await interaction.response.send_message("❌ You don't have enough Redmont Dollars to place this bet!", ephemeral=True)
        return
    
    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    
    if user_roll == bot_roll:
        winnings = bet * 2
        update_balance(interaction.user.id, winnings-bet)  # Net gain
        log_transaction(interaction.user.id, f"Rolled {user_roll}, Bot rolled {bot_roll}. Won ${winnings}")
        result = f"🎉 You rolled a {user_roll}, and the bot rolled a {bot_roll}. You win **${winnings}**!"
    else:
        update_balance(interaction.user.id, -bet)
        log_transaction(interaction.user.id, f"Rolled {user_roll}, Bot rolled {bot_roll}. Lost ${bet}")
        result = f"😞 You rolled a {user_roll}, and the bot rolled a {bot_roll}. You lose **${bet}**."
    
    embed = discord.Embed(title="🎲 Roll Dice 🎲", description=result, color=discord.Color.green() if user_roll == bot_roll else discord.Color.red())
    await interaction.response.send_message(embed=embed, ephemeral=True)




# Coinflip game
@tree.command(name="coinflip", description="Flip a coin and bet on heads or tails")
async def coinflip(interaction: discord.Interaction, bet: int, choice: str):
    user_id = interaction.user.id
    if choice.lower() not in ["heads", "tails"]:
        await interaction.response.send_message("⚠️ Choose either 'heads' or 'tails'!", ephemeral=True)
        return
    if bet <= 0 or bet > MAX_BET:
        await interaction.response.send_message(f"⚠️ Bet must be between 1 and {MAX_BET}!", ephemeral=True)
        return
    if bet > get_balance(user_id):
        await interaction.response.send_message("💸 You don't have enough Redmont Dollars!", ephemeral=True)
        return
    
    result = random.choice(["heads", "tails"])
    embed = discord.Embed(title="🪙 Coin Flip 🪙", description=f"The coin landed on **{result}**!", color=discord.Color.orange())
    
    if result == choice.lower():
        winnings = bet * 2
        update_balance(user_id, winnings-bet)  # Net gain
        log_transaction(user_id, f"Bet on {choice}, landed {result}. Won ${winnings}")
        embed.add_field(name="🎉 You Win!", value=f"You won **${winnings}**!", inline=False)
    else:
        update_balance(user_id, -bet)
        log_transaction(user_id, f"Bet on {choice}, landed {result}. Lost ${bet}")
        embed.add_field(name="😢 You Lost", value=f"You lost **${bet}**.", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)




# Blackjack game
class BlackjackGame:
    def __init__(self, user_id, bet):
        self.user_id = user_id
        self.bet = bet
        self.player_hand = [random.randint(1, 11), random.randint(1, 11)]
        self.bot_hand = [random.randint(1, 11), random.randint(1, 11)]
        self.game_over = False

    def hit(self):
        self.player_hand.append(random.randint(1, 11))
        if sum(self.player_hand) > 21:
            self.game_over = True
        return self.player_hand

    def stand(self):
        while sum(self.bot_hand) < 17:
            self.bot_hand.append(random.randint(1, 11))
        self.game_over = True
        return self.bot_hand

    def get_winner(self):
        player_total = sum(self.player_hand)
        bot_total = sum(self.bot_hand)
        if player_total > 21:
            return "bot"
        elif bot_total > 21 or player_total > bot_total:
            return "player"
        elif player_total < bot_total:
            return "bot"
        else:
            return "tie"

games = {}

class BlackjackView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id not in games:
            await interaction.response.send_message("⚠️ No active blackjack game found!", ephemeral=True)
            return

        game = games[user_id]
        game.hit()
        if game.game_over:
            winner = game.get_winner()
            result = "🎉 You win!" if winner == "player" else "😢 You lose." if winner == "bot" else "🤝 It's a tie!"
            if winner == "player":
                winnings = game.bet * 2
                update_balance(user_id, winnings-game.bet)  # Net gain
                log_transaction(user_id, f"Blackjack win: +${winnings}")
            else:
                log_transaction(user_id, f"Blackjack loss: -${game.bet}")
            del games[user_id]
            for item in self.children:
                item.disabled = True
        else:
            result = "Hit or Stand?"
        
        embed = discord.Embed(title="🃏 Blackjack 🃏", color=discord.Color.green())
        embed.add_field(name="Your Hand", value=f"{game.player_hand} (Total: {sum(game.player_hand)})", inline=False)
        embed.add_field(name="Bot's Hand", value=f"[{game.bot_hand[0]}, ?]", inline=False)
        embed.add_field(name="Game Status", value=result, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.danger)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id not in games:
            await interaction.response.send_message("⚠️ No active blackjack game found!", ephemeral=True)
            return

        game = games[user_id]
        game.stand()
        winner = game.get_winner()
        result = "🎉 You win!" if winner == "player" else "😢 You lose." if winner == "bot" else "🤝 It's a tie!"
        if winner == "player":
            winnings = game.bet * 2
            update_balance(user_id, winnings-game.bet)  # Net gain
            log_transaction(user_id, f"Blackjack win: +${winnings}")
        else:
            log_transaction(user_id, f"Blackjack loss: -${game.bet}")
        del games[user_id]
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(title="🃏 Blackjack 🃏", color=discord.Color.green())
        embed.add_field(name="Your Hand", value=f"{game.player_hand} (Total: {sum(game.player_hand)})", inline=False)
        embed.add_field(name="Bot's Hand", value=f"{game.bot_hand} (Total: {sum(game.bot_hand)})", inline=False)
        embed.add_field(name="Game Status", value=result, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

@tree.command(name="blackjack", description="Play a game of blackjack against the bot")
async def blackjack(interaction: discord.Interaction, bet: int):
    user_id = interaction.user.id
    if bet <= 0 or bet > MAX_BET:
        await interaction.response.send_message(f"⚠️ Bet must be between 1 and {MAX_BET}!", ephemeral=True)
        return
    if bet > get_balance(user_id):
        await interaction.response.send_message("💸 You don't have enough Redmont Dollars!", ephemeral=True)
        return

    games[user_id] = BlackjackGame(user_id, bet)
    game = games[user_id]
    update_balance(user_id, -bet)
    
    embed = discord.Embed(title="🃏 Blackjack 🃏", color=discord.Color.green())
    embed.add_field(name="Your Hand", value=f"{game.player_hand} (Total: {sum(game.player_hand)})", inline=False)
    embed.add_field(name="Bot's Hand", value=f"[{game.bot_hand[0]}, ?]", inline=False)
    embed.add_field(name="Game Status", value="Hit or Stand?", inline=False)
    
    view = BlackjackView(user_id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)




# Graceful shutdown function
def handle_shutdown():
    print("🔴 Saving data before shutdown...")
    save_data(BALANCES_FILE, balances)
    save_data(TRANSACTIONS_FILE, transactions)
    print("✅ Data saved successfully. Bot is shutting down.")


# Shutdown command for admins
@tree.command(name="shutdown", description="Safely shutdown the bot (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def shutdown(interaction: discord.Interaction):
    await interaction.response.send_message("🔴 Shutting down the bot safely...", ephemeral=True)
    handle_shutdown()
    await bot.close()


# Auto-save task
async def auto_save_data():
    while True:
        await asyncio.sleep(10)
        save_data(BALANCES_FILE, balances)
        save_data(TRANSACTIONS_FILE, transactions)
        print("✅ Auto-saved balances and transactions.")


# Run the bot
@bot.event
async def on_ready():
    global balances, transactions  # Ensure global variables are updated

    # Load balances
    loaded_balances = load_data(BALANCES_FILE)
    if isinstance(loaded_balances, dict):
        balances.update(loaded_balances)  # Use update() instead of replacing the dict
        print("✅ Balances successfully loaded from file.")
    else:
        print("⚠️ Balances failed to load. Using default empty dictionary.")

    # Load transactions
    loaded_transactions = load_data(TRANSACTIONS_FILE)
    if isinstance(loaded_transactions, dict):
        transactions.update(loaded_transactions)
        print("✅ Transactions successfully loaded from file.")
    else:
        print("⚠️ Transactions failed to load. Using default empty dictionary.")

    await bot.tree.sync()
    print(f'✅ Logged in as {bot.user}')
    
    bot.loop.create_task(auto_save_data())  # Start auto-save task


bot.run(BOT_KEY)
