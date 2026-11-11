from typing import Annotated

from fastapi import Depends, Request

from app.services import AppContext


def get_ctx(request: Request) -> AppContext:
    ctx: AppContext = request.app.state.ctx
    return ctx


Ctx = Annotated[AppContext, Depends(get_ctx)]
