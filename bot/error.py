from discord.ext import commands
from datetime import datetime
import inspect

async def err_log(err: str, ctx: commands.Context):
    await ctx.send("Someghint went wrong")   
    current_time = datetime.now()
    formatted_time = current_time.strftime("[%Y-%m-%d %H:%M:%S]")
    caller = inspect.currentframe().f_back
    caller_name = caller.f_code.co_name if caller else None
    print(f"{formatted_time} [{caller_name}] : {err}")