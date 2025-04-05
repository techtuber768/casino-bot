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
STAFF_CHANNEL_ID = 1358055200748998816

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
@bot.tree.command(name="balance", description="Check your balance")
async def balance(interaction: discord.Interaction):
    user_id = interaction.user.id
    balance = get_balance(user_id)
    await interaction.response.send_message(f"💰 Your balance is `${balance}` Redmont Dollars.", ephemeral=True)


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
                update_balance(user_id, winnings)
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
            update_balance(user_id, winnings)
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
        await asyncio.sleep(3)
        save_data(BALANCES_FILE, balances)
        save_data(TRANSACTIONS_FILE, transactions)


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


#Deposit accept/reject
class DepositView(discord.ui.View):
    def __init__(self, user: discord.User, amount: int):
        super().__init__(timeout=None)
        self.user = user
        self.amount = amount

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ You don't have permission to do this.", ephemeral=True)
            return

        update_balance(self.user.id, self.amount)
        await interaction.response.edit_message(content=f"✅ Deposit of ${self.amount} accepted for {self.user.mention}.", view=None)
        await self.user.send(f"✅ Your deposit of ${self.amount} has been **accepted**!")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ You don't have permission to do this.", ephemeral=True)
            return

        await interaction.response.edit_message(content=f"❌ Deposit of ${self.amount} rejected for {self.user.mention}.", view=None)
        await self.user.send(f"❌ Your deposit of ${self.amount} has been **rejected**.")

@bot.tree.command(name="deposit", description="Submit a deposit request with proof")
@app_commands.describe(amount="Amount to deposit", proof="Upload a screenshot as proof")
async def deposit(interaction: discord.Interaction, amount: int, proof: discord.Attachment):
    if amount <= 0:
        await interaction.response.send_message("⚠️ Amount must be positive!", ephemeral=True)
        return

    embed = discord.Embed(title="💰 Deposit Request", color=discord.Color.gold())
    embed.add_field(name="User", value=interaction.user.mention, inline=False)
    embed.add_field(name="Amount", value=f"${amount}", inline=False)
    embed.set_image(url=proof.url)

    staff_channel = interaction.guild.get_channel(STAFF_CHANNEL_ID)
    await staff_channel.send(embed=embed, view=DepositView(interaction.user, amount))

    await interaction.response.send_message("✅ Your deposit request has been submitted for review.", ephemeral=True)


#Withdrawal accept/reject
class WithdrawalView(discord.ui.View):
    def __init__(self, user: discord.User, amount: int, ign: str):
        super().__init__(timeout=None)
        self.user = user
        self.amount = amount
        self.ign = ign

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ You don't have permission to do this.", ephemeral=True)
            return

        update_balance(self.user.id, -self.amount)
        await interaction.response.edit_message(content=f"✅ Withdrawal of ${self.amount} approved for {self.user.mention}.", view=None)
        await self.user.send(f"✅ Your withdrawal of ${self.amount} has been **approved**!\nIn-game name: `{self.ign}`")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("⛔ You don't have permission to do this.", ephemeral=True)
            return

        await interaction.response.edit_message(content=f"❌ Withdrawal of ${self.amount} rejected for {self.user.mention}.", view=None)
        await self.user.send(f"❌ Your withdrawal of ${self.amount} has been **rejected**.")

@bot.tree.command(name="withdraw", description="Submit a withdrawal request")
@app_commands.describe(amount="Amount to withdraw", ign="Your in-game name")
async def withdraw(interaction: discord.Interaction, amount: int, ign: str):
    await interaction.response.defer(ephemeral=True)  # ✅ lets the bot "think" longer

    if amount <= 0:
        await interaction.followup.send("⚠️ Amount must be positive!", ephemeral=True)
        return

    balance = get_balance(interaction.user.id)

    if balance < amount:
        await interaction.followup.send("❌ You don't have enough Redmont Dollars.", ephemeral=True)
        return

    embed = discord.Embed(title="🏦 Withdrawal Request", color=discord.Color.red())
    embed.add_field(name="User", value=interaction.user.mention, inline=False)
    embed.add_field(name="Amount", value=f"${amount}", inline=False)
    embed.add_field(name="IGN", value=ign, inline=False)

    staff_channel = interaction.guild.get_channel(STAFF_CHANNEL_ID)
    await staff_channel.send(embed=embed, view=WithdrawalView(interaction.user, amount, ign))

    await interaction.followup.send("✅ Your withdrawal request has been submitted for review.", ephemeral=True)


#Slots games
EMOJIS = ["🍒", "🍋", "🍉", "⭐", "🔔", "🍇"]
class SlotsView(discord.ui.View):
    def __init__(self, user: discord.User, bet: int, multiplier: float, message: discord.Message):
        super().__init__(timeout=60)
        self.user = user
        self.bet = bet
        self.multiplier = multiplier
        self.message = message

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary)
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("⚠️ This button isn't for you!", ephemeral=True)
            return

        balance = get_balance(self.user.id)
        if balance < self.bet:
            await interaction.response.send_message("❌ Not enough Redmont Dollars to play again.", ephemeral=True)
            return

        await interaction.response.defer()  # Acknowledge button press

        for _ in range(3):
            spinning = " | ".join(random.choices(EMOJIS, k=3))
            await self.message.edit(content=f"🎰 {spinning}")
            await asyncio.sleep(0.4)

        result = [random.choice(EMOJIS) for _ in range(3)]
        result_str = " | ".join(result)

        if result[0] == result[1] == result[2]:
            winnings = int(self.bet * self.multiplier)
            update_balance(self.user.id, winnings)
            message = f"🎉 You won! You got **{result_str}**\n💵 You earned **${winnings}** Redmont Dollars!"
            next_multiplier = 1.5
        else:
            update_balance(self.user.id, -self.bet)
            message = f"😢 You lost. You got **{result_str}**\nBetter luck next time!"
            next_multiplier = 2.0

        await self.message.edit(content=message, view=SlotsView(self.user, self.bet, next_multiplier, self.message))

@bot.tree.command(name="slots", description="Play the slot machine!")
@app_commands.describe(bet="Amount to bet")
async def slots(interaction: discord.Interaction, bet: int):
    if bet <= 0:
        await interaction.response.send_message("⚠️ Bet must be greater than zero.", ephemeral=True)
        return

    balance = get_balance(interaction.user.id)
    if balance < bet:
        await interaction.response.send_message("❌ You don't have enough Redmont Dollars.", ephemeral=True)
        return

    await interaction.response.send_message("🎰 Spinning...", ephemeral=True)
    message = await interaction.original_response()

    for _ in range(3):
        spinning = " | ".join(random.choices(EMOJIS, k=3))
        await message.edit(content=f"🎰 {spinning}")
        await asyncio.sleep(0.4)

    result = [random.choice(EMOJIS) for _ in range(3)]
    result_str = " | ".join(result)

    if result[0] == result[1] == result[2]:
        winnings = bet * 2
        update_balance(interaction.user.id, winnings)
        msg_text = f"🎉 You won! You got **{result_str}**\n💵 You earned **${winnings}** Redmont Dollars!"
        multiplier = 1.5
    else:
        update_balance(interaction.user.id, -bet)
        msg_text = f"😢 You lost. You got **{result_str}**\nBetter luck next time!"
        multiplier = 2.0

    await message.edit(content=msg_text, view=SlotsView(interaction.user, bet, multiplier, message))


#Rock Paper Scissors game
class RPSButtons(discord.ui.View):
    def __init__(self, user_id, bet):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.bet = bet
        self.play_ended = False

    async def play_rps(self, interaction: discord.Interaction, user_choice: str):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return

        choices = ["🪨", "📄", "✂️"]
        bot_choice = random.choice(choices)
        outcome = self.determine_winner(user_choice, bot_choice)
        result_message = f"You chose {user_choice} | Bot chose {bot_choice}\n"

        if outcome == "win":
            winnings = self.bet * 2
            update_balance(self.user_id, winnings)
            result_message += f"🎉 You won {winnings} Redmont Dollars!"
        elif outcome == "lose":
            result_message += f"😢 You lost {self.bet} Redmont Dollars!"
        else:
            update_balance(self.user_id, self.bet)
            result_message += "🤝 It's a tie! Your bet has been returned."

        self.clear_items()
        self.add_item(PlayAgainButton(self.user_id, self.bet))
        await interaction.response.edit_message(content=result_message, view=self)
        self.play_ended = True

    def determine_winner(self, user, bot):
        wins = {"🪨": "✂️", "📄": "🪨", "✂️": "📄"}
        if user == bot:
            return "tie"
        elif wins[user] == bot:
            return "win"
        else:
            return "lose"

    @discord.ui.button(label="🪨", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_rps(interaction, "🪨")

    @discord.ui.button(label="📄", style=discord.ButtonStyle.primary)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_rps(interaction, "📄")

    @discord.ui.button(label="✂️", style=discord.ButtonStyle.primary)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_rps(interaction, "✂️")

class PlayAgainButton(discord.ui.Button):
    def __init__(self, user_id, bet):
        super().__init__(label="🔁 Play Again", style=discord.ButtonStyle.success)
        self.user_id = user_id
        self.bet = bet

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("You can't restart someone else's game!", ephemeral=True)
            return

        balance = get_balance(self.user_id)
        if balance < self.bet:
            await interaction.response.send_message("❌ You don't have enough Redmont Dollars to play again.", ephemeral=True)
            return

        update_balance(self.user_id, -self.bet)
        view = RPSButtons(user_id=self.user_id, bet=self.bet)
        await interaction.response.edit_message(content="Let's play again!\nChoose your move:", view=view)

@bot.tree.command(name="rps", description="Play Rock Paper Scissors and win Redmont Dollars!")
@app_commands.describe(bet="Amount of Redmont Dollars to bet")
async def rps(interaction: discord.Interaction, bet: int):
    user_id = str(interaction.user.id)
    balance = get_balance(user_id)

    if bet <= 0:
        await interaction.response.send_message("❌ Bet must be greater than 0.", ephemeral=True)
        return

    if balance < bet:
        await interaction.response.send_message("❌ You don't have enough Redmont Dollars!", ephemeral=True)
        return

    update_balance(user_id, -bet)
    view = RPSButtons(user_id=user_id, bet=bet)

    await interaction.response.send_message(
        content="Let's play Rock Paper Scissors!\nChoose your move:",
        view=view,
        ephemeral=True
    )



#HighLow Game
# === High-Low Game Logic ===
card_values = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 11, "Q": 12, "K": 13, "A": 14
}

# === Pay Table ===
pay_table = {  # ← Pay table for win multiplier
    1: 1.0,
    2: 1.2,
    3: 1.4,
    4: 1.6,
    5: 1.8,
    6: 2.0,
    7: 2.5,
    8: 3.0,
    9: 4.0,
    10: 5.0,
    11: 7.0,
    12: 10.0,
    13: 15.0
}

def draw_card():
    return random.choice(list(card_values.keys()))

class HighLowButtons(discord.ui.View):
    def __init__(self, user_id, bet, current_card):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.bet = bet
        self.current_card = current_card

    async def play_highlow(self, interaction, choice):
        new_card = draw_card()
        old_val = card_values[self.current_card]
        new_val = card_values[new_card]

        outcome = "win" if (choice == "higher" and new_val > old_val) or (choice == "lower" and new_val < old_val) else "lose"

        multiplier = pay_table[abs(old_val - new_val)] if outcome == "win" else 0
        winnings = int(self.bet * multiplier)

        update_balance(self.user_id, winnings)

        msg = (
            f"🎴 Your card: `{self.current_card}`\n"
            f"🃏 New card: `{new_card}`\n"
            f"💸 Result: {'🎉 You won' if outcome == 'win' else '😢 You lost'} {f'`+${winnings}`' if winnings else ''}"
        )

        view = PlayAgainView(self.user_id, self.bet)
        await interaction.response.edit_message(content=msg, view=view)

    @discord.ui.button(label="Higher", style=discord.ButtonStyle.primary, emoji="🔼")
    async def higher(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("🚫 You can't play this game!", ephemeral=True)
        await self.play_highlow(interaction, "higher")

    @discord.ui.button(label="Lower", style=discord.ButtonStyle.primary, emoji="🔽")
    async def lower(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("🚫 You can't play this game!", ephemeral=True)
        await self.play_highlow(interaction, "lower")

class PlayAgainView(discord.ui.View):
    def __init__(self, user_id, bet):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.bet = bet

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.success, emoji="🔁")
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("🚫 Only you can restart your game.", ephemeral=True)

        balance = get_balance(self.user_id)
        if self.bet > balance:
            return await interaction.response.send_message("❌ You don't have enough balance to play again.", ephemeral=True)

        update_balance(self.user_id, -self.bet)

        card = draw_card()
        view = HighLowButtons(self.user_id, self.bet, card)
        await interaction.response.send_message(
            content=f"🎴 Your card is `{card}`\nWill the next card be 🔼 higher or 🔽 lower?",
            view=view,
            ephemeral=True
        )

# === Slash Command for High-Low ===
@bot.tree.command(name="highlow", description="Play High-Low card game!")
@app_commands.describe(bet="How much you want to bet")
async def highlow(interaction: discord.Interaction, bet: int):
    user_id = interaction.user.id
    balance = get_balance(user_id)

    if bet <= 0:
        return await interaction.response.send_message("❌ Bet must be greater than 0.", ephemeral=True)

    if bet > balance:
        return await interaction.response.send_message("❌ You don't have enough balance to bet that amount.", ephemeral=True)

    update_balance(user_id, -bet)

    card = draw_card()
    view = HighLowButtons(user_id, bet, card)

    await interaction.response.send_message(
        content=f"🎴 Your card is `{card}`\nWill the next card be 🔼 higher or 🔽 lower?",
        view=view,
        ephemeral=True
    )



bot.run(BOT_KEY)
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot is online as {bot.user}")
