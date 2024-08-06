import os
import numpy as np
from pydub import AudioSegment
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import BadRequest
import subprocess 

# Initialize the bot with your credentials
api_id = '10811400'
api_hash = '191bf5ae7a6c39771e7b13cf4ffd1279'
bot_token = '7412278588:AAFKWhBga4p9sqXT9OcaYt41nQz14IVmQyA'

app = Client("slowreverb_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)


# Initialize the metadata dictionary
metadata = {
    "comment": "Default comment",
    "created_by": "Default creator",
    "title": "Default title"
}

@app.on_message(filters.command("setmetadata") & filters.private)
async def set_metadata_command(client, msg):
    # Extract metadata from the command message
    if len(msg.command) < 2:
        await msg.reply_text("Invalid command format. Use: /setmetadata comment | created_by | title")
        return
    
    parts = msg.text.split(" ", 1)[1].split(" | ")
    if len(parts) != 3:
        await msg.reply_text("Invalid number of metadata parts. Use: /setmetadata comment | created_by | title")
        return
    
    # Store the metadata locally
    metadata["comment"] = parts[0].strip()
    metadata["created_by"] = parts[1].strip()
    metadata["title"] = parts[2].strip()
    
    await msg.reply_text("Metadata set successfully ✅.")

def change_audio_metadata(input_path, output_path, comment, created_by, audio_title):
    command = [
        'ffmpeg',
        '-i', input_path,
        '-metadata', f'comment={comment}',
        '-metadata', f'artist={created_by}',
        '-metadata', f'title={audio_title}',
        '-c', 'copy',
        output_path,
        '-y'
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise Exception(f"FFmpeg error: {stderr.decode('utf-8')}")

def apply_slowreverb(audio_path, output_path, room_size=0.75, damping=0.5, wet_level=0.08, dry_level=0.2, slowfactor=0.08):
    # Convert to WAV if needed
    if not audio_path.lower().endswith('.wav'):
        tmp_wav = "tmp.wav"
        sp.call(f'ffmpeg -hide_banner -loglevel error -y -i "{audio_path}" "{tmp_wav}"', shell=True)
        audio_path = tmp_wav
    
    # Load the audio file
    audio = AudioSegment.from_wav(audio_path)
    audio = audio.set_channels(2)  # Ensure the audio is stereo

    # Slow down the audio
    slowed_audio = audio._spawn(audio.raw_data, overrides={
        "frame_rate": int(audio.frame_rate * (1 - slowfactor))
    })
    slowed_audio = slowed_audio.set_frame_rate(audio.frame_rate)

    # Export to temporary file
    temp_file = "temp_reverb.wav"
    slowed_audio.export(temp_file, format="wav")

    # Apply reverb using ffmpeg
    reverb_command = (
        f'ffmpeg -hide_banner -loglevel error -y -i "{temp_file}" '
        f'-af "aecho={wet_level}:{damping}:{room_size}:{dry_level}" "{output_path}"'
    )
    sp.call(reverb_command, shell=True)

    # Cleanup temporary files
    os.remove(temp_file)
    if audio_path == "tmp.wav":
        os.remove(audio_path)

@app.on_message(filters.command("slowreverb") & filters.private)
async def slow_reverb_handler(client: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.audio:
        await message.reply_text("Please reply to an audio file with the /slowreverb command.")
        return

    # Inform user about processing time
    await message.reply_text("Processing your request. Please wait for 2 to 4 minutes.")

    audio = message.reply_to_message.audio
    file_path = await client.download_media(audio)
    input_file = file_path
    output_file = f"{os.path.splitext(file_path)[0]}_slowreverb.wav"

    # Apply the slow reverb effect
    apply_slowreverb(input_file, output_file)

    # Convert the output to FLAC with 24-bit depth and 48kHz sample rate
    final_output = f"{os.path.splitext(file_path)[0]}_slowreverb_24bit_48kHz.flac"
    sp.call(f'ffmpeg -hide_banner -loglevel error -y -i "{output_file}" -sample_fmt s32 -ar 48000 "{final_output}"', shell=True)

    # Add metadata to the final FLAC file
    change_audio_metadata(final_output, final_output, metadata["comment"], metadata["created_by"], metadata["title"])

    # Cleanup intermediate files
    os.remove(file_path)
    os.remove(output_file)
    
    try:
        await message.reply_audio(audio=final_output)
    except Exception as e:
        await message.reply_text(f"Failed to send audio: {e}")
    
    os.remove(final_output)

    
if __name__ == "__main__":
    app.run()
