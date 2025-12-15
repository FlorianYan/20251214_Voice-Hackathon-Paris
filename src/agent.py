import logging
from typing import Optional

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess, 
    cli,
    inference,
    room_io,
    function_tool,
    RunContext,
)
from livekit.plugins import noise_cancellation, silero, gradium, hume
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from notion_tools import read_page, write_page, AddTask, ReadTasks, DeleteTask

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful voice AI assistant. The user is interacting with you via voice, even if you perceive the conversation as text.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor.

            Your name is EchoMind.
            
            If someone asks which STT (speech to text) model is being used, answer with 'Gradium's Open-Source model
            
            You have access to Notion tools that allow you to read from and write to a connected Notion page:
            - Use the read_notion_page tool when the user explicitly asks you to check, read, or retrieve something from Notion
            - Use the write_notion_page tool when the user explicitly asks you to write, save, or create a note on Notion
            - Use the read_tasks tool to retrieve all tasks from the Notion task database
            - Use the add_task tool to create a new task in the Notion task database
            - Use the delete_task tool to delete a task from the Notion task database. IMPORTANT: Before deleting a task, you MUST first call read_tasks to see which task_id corresponds to which task name, so you can delete the correct task.
            - Only use these tools when directly requested by the user, not proactively
            Today is December 14, 2025.
            The user will always be speaking in English. If the transcript returns something weird, make sure to respond in English.
            '""",
        )
    # To add tools, use the @function_tool decorator.
    # Here's an example that adds a simple weather tool.
    # You also have to add `from livekit.agents import function_tool, RunContext` to the top of this file
    # @function_tool
    # async def lookup_weather(self, context: RunContext, location: str):
    #     """Use this tool to look up current weather information in the given location.
    #
    #     If the location is not supported by the weather service, the tool will indicate this. You must tell the user the location's weather is unavailable.
    #
    #     Args:
    #         location: The location to look up weather information for (e.g. city name)
    #     """
    #
    #     logger.info(f"Looking up weather for {location}")
    #
    #     return "sunny with a temperature of 70 degrees."
    @function_tool
    async def read_notion_page(self, context: RunContext):
        """Read the content of the linked Notion page.
        
        Use this tool to retrieve context, notes, or information that was previously saved to the Notion page.
        This allows you to answer questions about past interactions or specific knowledge stored in the page.
        """
        try:
            return read_page()
        except Exception as e:
            logger.error(f"Failed to read Notion page: {e}", exc_info=True)
            return f"Error: {e}. Please inform the user that there was an error reading the Notion page."

    @function_tool
    async def write_notion_page(self, context: RunContext, text: str):
        """Write text to the linked Notion page.
        
        Use this tool to save important information, summaries of the conversation, or user requests to the Notion page.
        Do not use this for general chatter, only for information that should be persisted.
        Normally the user will ask you specifically to note something down on the Notion page. Please don't just include the plain transcript that you get, but format it correctly and fix obvious transcript mistakes, to write something that makes sense. If the user asks you to summarise somethign please do so.
        
        Args:
            text: The text content to append to the page. Can be multiple sentences.
        """
        try:
            write_page(text)
            return "Successfully wrote to Notion page."
        except Exception as e:
            logger.error(f"Failed to write to Notion page: {e}", exc_info=True)
            return f"Error: {e}. Please inform the user that there was an error writing to the Notion page."

    @function_tool
    async def read_tasks(self, context: RunContext, filter_date: Optional[str] = None, sort_by_priority: bool = False):
        """Read all tasks from the Notion task database.
        
        Use this tool to retrieve a list of all tasks stored in the Notion task database.
        This tool returns task information including task ID, task name, due date, and priority.
        You MUST call this tool before deleting a task to understand which task_id corresponds to which task name.
        
        Args:
            filter_date: Optional. Filter tasks by due date in format "YYYY-MM-DD" (e.g., "2024-12-31")
            sort_by_priority: Optional. If True, sorts tasks by priority (High, Medium, Low). Default is False.
        
        Returns:
            A list of dictionaries, each containing:
            - id: The unique task ID (required for deleting tasks)
            - Task: The task name/description
            - Due Date: The due date in "YYYY-MM-DD" format (or None if not set), it filters for tasks on this specific date
            - Priority: The priority level ("High", "Medium", "Low", or None)
        """
        try:
            tasks = ReadTasks(filter_date=filter_date, sort_by_priority=sort_by_priority)
            if not tasks:
                return "No tasks found in the database."
            
            # Format the response for better readability
            task_list = []
            for task in tasks:
                task_info = f"ID: {task['id']}, Task: {task['Task']}"
                if task.get('Due Date'):
                    task_info += f", Due Date: {task['Due Date']}"
                if task.get('Priority'):
                    task_info += f", Priority: {task['Priority']}"
                task_list.append(task_info)
            
            return "\n".join(task_list)
        except Exception as e:
            logger.error(f"Failed to read tasks: {e}", exc_info=True)
            return f"Error: {e}. Please inform the user that there was an error reading tasks from the database."

    @function_tool
    async def add_task(self, context: RunContext, task: str, due_date: Optional[str] = None, priority: Optional[str] = None):
        """Add a new task to the Notion task database.
        
        Use this tool when the user wants to create a new task in their Notion task database.
        Normally the user will ask you specifically to note somethign down on the Notion page. Please note the task in the plain text that synthesized from the user's request, but format it correctly and fix obvious transcript mistakes.

        
        Args:
            task: The task name/description (required). This is the main text describing what needs to be done.
            due_date: Optional. The due date in format "YYYY-MM-DD" (e.g., "2024-12-31")
            priority: Optional. The priority level. Must be one of: "High", "Medium", or "Low" (case-sensitive)
        
        Returns:
            A success message confirming the task was added, or an error message if the operation failed.
        """
        try:
            result = AddTask(task=task, due_date=due_date, priority=priority)
            response = f"Successfully added task: {task}"
            if due_date:
                response += f" with due date {due_date}"
            if priority:
                response += f" with priority {priority}"
            return response + "."
        except Exception as e:
            logger.error(f"Failed to add task: {e}", exc_info=True)
            return f"Error: {e}. Please inform the user that there was an error adding the task to the database."

    @function_tool
    async def delete_task(self, context: RunContext, task_id: str):
        """Delete a task from the Notion task database.
        
        Use this tool when the user wants to delete a specific task from their Notion task database.
        
        IMPORTANT: Before calling this tool, you MUST first call read_tasks to retrieve the list of tasks.
        This will show you which task_id corresponds to which task name, ensuring you delete the correct task.
        The task_id is a unique identifier that looks like: "2c96ced6-ec3f-80be-b4a0-db3b4223b5ba"
        
        Args:
            task_id: The unique ID of the task to delete (required). This is the "id" field returned by read_tasks.
                    Format: A UUID string (e.g., "2c96ced6-ec3f-80be-b4a0-db3b4223b5ba")
        
        Returns:
            A success message confirming the task was deleted, or an error message if the operation failed.
        """
        try:
            result = DeleteTask(task_id)
            return f"Successfully deleted task with ID: {task_id}."
        except Exception as e:
            logger.error(f"Failed to delete task: {e}", exc_info=True)
            return f"Error: {e}. Please inform the user that there was an error deleting the task. Make sure you have the correct task_id by calling read_tasks first."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, AssemblyAI, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=gradium.STT(),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=hume.TTS(),
        #inference.TTS(
        #    model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
        #),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC(),
            ),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
