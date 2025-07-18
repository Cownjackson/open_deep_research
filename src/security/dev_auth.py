"""
Development authentication - bypasses Supabase for local development
"""
import os
from langgraph_sdk import Auth
from langgraph_sdk.auth.types import StudioUser

# The "Auth" object is a container that LangGraph will use to mark our authentication function
auth = Auth()

@auth.authenticate
async def get_current_user(authorization: str | None) -> Auth.types.MinimalUserDict:
    """Simple development authentication - allows any request."""
    
    # For development, we'll accept any authorization or no authorization
    # and return a dummy user
    return {
        "identity": "dev-user",
    }

@auth.on.threads.create
@auth.on.threads.create_run
async def on_thread_create(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.threads.create.value,
):
    """Add owner when creating threads for development."""
    if isinstance(ctx.user, StudioUser):
        return

    # Add owner metadata to the thread being created
    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity

@auth.on.threads.read
@auth.on.threads.delete
@auth.on.threads.update
@auth.on.threads.search
async def on_thread_read(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.threads.read.value,
):
    """Allow reading threads for development."""
    if isinstance(ctx.user, StudioUser):
        return
    
    return {"owner": ctx.user.identity}

@auth.on.assistants.create
async def on_assistants_create(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.assistants.create.value,
):
    if isinstance(ctx.user, StudioUser):
        return

    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity

@auth.on.assistants.read
@auth.on.assistants.delete
@auth.on.assistants.update
@auth.on.assistants.search
async def on_assistants_read(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.assistants.read.value,
):
    """Allow reading assistants for development."""
    if isinstance(ctx.user, StudioUser):
        return

    return {"owner": ctx.user.identity}

@auth.on.store()
async def authorize_store(ctx: Auth.types.AuthContext, value: dict):
    if isinstance(ctx.user, StudioUser):
        return

    # For development, allow all store operations
    namespace: tuple = value["namespace"]
    # Don't enforce ownership in development
    pass