from typing import Callable, Any
from dataclasses import dataclass
from selenium.webdriver.common.by import By


@dataclass
class InputField:
    attr: By
    attrValue: str
    value: str
    afterEnter: bool = False


@dataclass
class ActionButton:
    attr: By = None
    attrValue: str = None
    wait: Any = None  # EC.presence_of_element_located(...)
    afterWait: Any = None
    waitAfterAction: Callable = None
