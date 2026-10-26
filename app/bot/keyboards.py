from maxapi.types import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


def role_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Я учитель", payload="role_teacher"),
        CallbackButton(text="Я ученик", payload="role_student"),
    )
    builder.row(CallbackButton(text="Помощь", payload="help"))
    return builder.as_markup()


def teacher_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Загрузить материалы", payload="upload_book"))
    builder.row(CallbackButton(text="Удалить материалы", payload="delete_materials"))
    builder.row(CallbackButton(text="Статистика", payload="stats"))
    builder.row(CallbackButton(text="Сменить роль", payload="change_role"))
    return builder.as_markup()


def student_after_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Подробнее", payload="more"))
    builder.row(CallbackButton(text="Сменить класс и предмет", payload="pick_material"))
    builder.row(CallbackButton(text="Сменить роль", payload="change_role"))
    return builder.as_markup()


def teacher_after_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Подробнее", payload="more"))
    builder.row(CallbackButton(text="Панель управления", payload="panel"))
    builder.row(CallbackButton(text="Сменить роль", payload="change_role"))
    return builder.as_markup()


def change_role_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Сменить роль", payload="change_role"))
    return builder.as_markup()


def back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Назад", payload="back"))
    return builder.as_markup()


def enter_another_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Загрузить еще один материал", payload="change_role"))
    builder.row(CallbackButton(text="Сменить роль", payload="change_role"))
    return builder.as_markup()

def help_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Я учитель", payload="role_teacher"),
        CallbackButton(text="Я ученик", payload="role_student"),
    )
    return builder.as_markup()