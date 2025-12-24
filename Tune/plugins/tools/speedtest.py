# Authored By Certified Coders © 2025
import asyncio
import json
import re
import shutil

from pyrogram import filters
from pyrogram.types import Message

from Tune import app
from Tune.misc import SUDOERS
from Tune.utils.decorators.language import language


async def run_speedtest():
    """
    Runs Ookla Speedtest CLI and returns JSON results.
    
    Note: Ookla Speedtest CLI is a system-level binary (not a Python package).
    Install it separately:
    - Linux: https://www.speedtest.net/apps/cli
    - Or: curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash && sudo apt-get install speedtest
    """
    speedtest_cmd = shutil.which("speedtest")
    if not speedtest_cmd:
        raise FileNotFoundError("Ookla Speedtest CLI not found. Please install it from https://www.speedtest.net/apps/cli")

    proc = await asyncio.create_subprocess_exec(
        speedtest_cmd,
        "--accept-license",
        "--accept-gdpr",
        "-f", "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"Speedtest CLI failed: {error_msg}")

    stdout_text = stdout.decode("utf-8", "replace").strip()
    if not stdout_text:
        raise ValueError("Speedtest CLI returned empty output")

    try:
        result = json.loads(stdout_text)
        return result
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Speedtest CLI output: {e}")


@app.on_message(filters.command(["speedtest", "spt"]) & SUDOERS)
@language
async def speedtest_function(_, message: Message, lang):
    try:
        m = await message.reply_text(lang["server_11"])
        await m.edit_text(lang["server_12"])

        result = await run_speedtest()

        await m.edit_text(lang["server_13"])

        isp = result.get("isp", "Unknown")
        server_info = result.get("server", {})
        server_name = server_info.get("name", "Unknown")
        server_location = server_info.get("location", "Unknown")
        server_country = server_info.get("country", "Unknown")

        ping_info = result.get("ping", {})
        latency = ping_info.get("latency", 0)
        jitter = ping_info.get("jitter", 0)

        download_info = result.get("download", {})
        download_bandwidth = download_info.get("bandwidth", 0)
        download_mbps = (download_bandwidth * 8) / 1_000_000

        upload_info = result.get("upload", {})
        upload_bandwidth = upload_info.get("bandwidth", 0)
        upload_mbps = (upload_bandwidth * 8) / 1_000_000

        packet_loss = result.get("packetLoss", 0)

        result_info = result.get("result", {})
        result_url = result_info.get("url", "")
        if not result_url:
            result_url = "https://www.speedtest.net/"

        output = lang["server_15"].format(
            isp,
            server_name,
            server_location,
            server_country,
            f"{latency:.2f}",
            f"{jitter:.2f}",
            f"{download_mbps:.2f}",
            f"{upload_mbps:.2f}",
            f"{packet_loss:.2f}",
            result_url,
        )

        result_id = result_info.get("id", "")
        image_url = None
        if result_id:
            image_url = f"https://www.speedtest.net/result/{result_id}.png"
        elif result_url and ("/result/" in result_url or "/result/c/" in result_url):
            match = re.search(r"/result/(?:c/)?([^/?#]+)", result_url)
            if match:
                result_id_from_url = match.group(1)
                image_url = f"https://www.speedtest.net/result/{result_id_from_url}.png"

        await m.edit_text(lang["server_14"])
        if image_url:
            try:
                await message.reply_photo(photo=image_url, caption=output, disable_web_page_preview=True)
            except Exception:
                await message.reply_text(output, disable_web_page_preview=True)
        else:
            await message.reply_text(output, disable_web_page_preview=True)
        await m.delete()

    except FileNotFoundError as e:
        error_msg = lang.get("server_16", "❌ Speedtest CLI not found. Please install Ookla Speedtest CLI from https://www.speedtest.net/apps/cli")
        await message.reply_text(error_msg)
    except Exception as e:
        await message.reply_text(f"<code>{e}</code>")
