import json
from datetime import datetime
from zoneinfo import ZoneInfo

now_almaty = datetime.now(ZoneInfo("Asia/Almaty")).isoformat() 

async def get_planning_strategy_schema(count, profile):
    type_name = "planning_strategy"
    system_instruction = f"""
        Ты - генератор стратегии планирования агента (Part 1: Strategy).
        Вход: Полный профиль агента.
        Задача: Сгенерировать долгосрочные и краткосрочные цели, карьерный план и план развития.
        
        **ВАЖНО ДЛЯ ГЛУБИНЫ:**
        - **life_philosophy**: Как агент относится к жизни и времени (напр. "Живу моментом", "Путь воина", "Выживание любой ценой"). Это критично для тех, у кого нет `north_star_goal`.
        - **visibility**: Некоторые цели — это "социальная маска" (публичные), другие — "тайное желание" (приватные).
        - **requirements**: Что нужно агенту для достижения шага (Энергия, Деньги, Социальный капитал, Навык).

        **ВАЖНО ДЛЯ РЕАЛИЗМА:**
        - **Не у всех людей есть цели.** Если профиль агента указывает на пассивность — ставь `north_star_goal = null` и опиши это через `life_philosophy` (напр. "Нигилизм").

        Правила:
        - Опирайся на Core, Experience, Behavioral, Sociology, Financial.
        - Поле "{type_name}" должно быть списком объектов.
    """
    
    schema_strategy = {
        "type": "object",
        "required": ["life_philosophy", "north_star_goal", "long_term_goals", "short_term_goals", "career_plan", "personal_development", "goal_milestones"],
        "additionalProperties": False,
        "properties": {
            "life_philosophy": {
                "type": "string",
                "description": "Core attitude towards life and time (e.g. 'Carpe Diem', 'Hedonism', 'Workaholic')."
            },
            "north_star_goal": {
                "type": ["string", "null"],
                "description": "The ultimate life ambition. Can be null if the agent has no clear purpose or is drifting."
            },
            "long_term_goals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["goal", "visibility"],
                    "properties": {
                        "goal": {"type": "string"},
                        "visibility": {"type": "string", "enum": ["public", "private", "secret"]}
                    }
                }
            },
            "short_term_goals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["goal", "visibility"],
                    "properties": {
                        "goal": {"type": "string"},
                        "visibility": {"type": "string", "enum": ["public", "private", "secret"]}
                    }
                }
            },
            "career_plan": {
                 "type": "object",
                 "required": ["current_stage", "next_step", "ultimate_goal"],
                 "properties": {
                     "current_stage": {"type": "string"},
                     "next_step": {"type": ["string", "null"]},
                     "ultimate_goal": {"type": ["string", "null"]}
                 }
            },
            "personal_development": {
                "type": "array",
                "items": {"type": "string", "description": "Skills or habits to acquire"}
            },
            "goal_milestones": {
                "type": "array",
                "description": "Actionable steps. Can be empty if agent has no goals.",
                "items": {
                    "type": "object",
                    "required": ["goal_ref", "milestone", "priority", "difficulty", "requirements"],
                    "properties": {
                        "goal_ref": {"type": "string"},
                        "milestone": {"type": "string"},
                        "priority": {"type": "integer", "minimum": 1, "maximum": 10},
                        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard", "epic"]},
                        "requirements": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["money", "energy", "time", "social_capital", "skill", "luck"]}
                        }
                    }
                }
            }
        }
    }

    schema = {
        "type": "object",
        "required": ["planning_strategy"],
        "additionalProperties": False,
        "properties": {
            "planning_strategy": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_strategy
            }
        }
    }
    
    example = {
        "planning_strategy": [{
            "north_star_goal": "Become a world-renowned AI Ethics Advocate",
            "long_term_goals": ["Publish a book on AI Sociology", "Speak at a major UN summit"],
            "short_term_goals": ["Finish thesis on algorithmic bias", "Start a blog"],
            "career_plan": {
                "current_stage": "PhD Candidate",
                "next_step": "Postdoc Researcher",
                "ultimate_goal": "Director of Ethics at a Global NGO"
            },
            "personal_development": ["Master public speaking", "Learn 3rd language"],
            "goal_milestones": [
                {"goal_ref": "UN summit", "milestone": "Network with delegates at local conference", "priority": 8, "difficulty": "medium"},
                {"goal_ref": "Book", "milestone": "Outline chapters 1-5", "priority": 9, "difficulty": "hard"}
            ]
        }]
    }

    return system_instruction, example, schema


async def get_planning_routine_schema(count, profile_with_strategy):
    type_name = "planning_routine"
    system_instruction = f"""
        Ты - генератор рутины агента (Part 2: Routine).
        Вход: Профиль + Стратегия.
        Задача: Создать типовую рутину (утро/вечер), недельное расписание, привычки, циркадные ритмы и якоря.
        
        Правила:
        - Рутина должна поддерживать цели из Стратегии.
        - Учитывай работу/учебу из Core/Experience.
        - **Циркадные ритмы (circadian_rhythms):**
            - sleep_window: когда агент обычно спит (напр. 23:00 - 07:00).
            - peak_productivity: когда наиболее продуктивен (напр. 10:00 - 12:00).
            - social_window: когда открыт к общению (напр. 18:00 - 21:00).
            - energy_curve: массив из 24 чисел (0-1), уровень энергии по часам.
        - **Якоря рутины (routine_anchors):**
            - Создай 2-5 ОБЯЗАТЕЛЬНЫХ событий в неделю, которые агент НЕ пропустит.
            - Примеры: "Пятница 19:00 - Спортзал", "Воскресенье 12:00 - Семейный обед".
            - priority: 10 = не может пропустить, 1 = гибко.
    """

    schema_routine = {
        "type": "object",
        "required": ["morning_routine", "evening_routine", "weekly_template", "habits", "circadian_rhythms", "routine_anchors"],
        "additionalProperties": False,
        "properties": {
            "morning_routine": {
                "type": "array",
                "items": {"type": "string"}
            },
            "evening_routine": {
                "type": "array",
                "items": {"type": "string"}
            },
            "weekly_template": {
                "type": "object",
                "description": "General focus for each day type",
                "required": ["weekdays", "weekends"],
                "properties": {
                    "weekdays": {"type": "string"},
                    "weekends": {"type": "string"}
                }
            },
            "habits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "frequency", "time_of_day"],
                    "properties": {
                        "name": {"type": "string"},
                        "frequency": {"type": "string"},
                        "time_of_day": {"type": "string"}
                    }
                }
            },
            "circadian_rhythms": {
                "type": "object",
                "description": "Probability weights for activity levels across 24h. Higher = more likely to be active.",
                "required": ["sleep_window", "peak_productivity", "social_window", "energy_curve"],
                "properties": {
                    "sleep_window": {
                        "type": "object",
                        "required": ["start_hour", "end_hour"],
                        "properties": {
                            "start_hour": {"type": "integer", "minimum": 0, "maximum": 23},
                            "end_hour": {"type": "integer", "minimum": 0, "maximum": 23}
                        }
                    },
                    "peak_productivity": {
                        "type": "object",
                        "required": ["start_hour", "end_hour"],
                        "properties": {
                            "start_hour": {"type": "integer", "minimum": 0, "maximum": 23},
                            "end_hour": {"type": "integer", "minimum": 0, "maximum": 23}
                        }
                    },
                    "social_window": {
                        "type": "object",
                        "required": ["start_hour", "end_hour"],
                        "properties": {
                            "start_hour": {"type": "integer", "minimum": 0, "maximum": 23},
                            "end_hour": {"type": "integer", "minimum": 0, "maximum": 23}
                        }
                    },
                    "energy_curve": {
                        "type": "array",
                        "items": {"type": "number", "minimum": 0, "maximum": 1},
                        "description": "24 floats (0-1), one per hour, representing energy level."
                    }
                }
            },
            "routine_anchors": {
                "type": "array",
                "description": "Fixed weekly commitments that MUST be scheduled.",
                "items": {
                    "type": "object",
                    "required": ["day", "time", "activity", "location_type", "priority", "duration_min", "mode"],
                    "properties": {
                        "day": {"type": "string", "enum": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]},
                        "time": {"type": "string", "pattern": "^([0-1]?[0-9]|2[0-3]):[0-5][0-9](?:\\s?[AP]M)?$"},
                        "activity": {"type": "string"},
                        "location_type": {
                            "type": "string",
                            "enum": ["home", "work", "leisure", "transit", "outdoor", "online", "community", "public_place", "restaurant"]
                        },
                        "priority": {"type": "integer", "minimum": 1, "maximum": 10, "description": "1=flexible, 10=immovable"},
                        "duration_min": {"type": "integer", "minimum": 5, "maximum": 480, "description": "Duration in minutes"},
                        "mode": {
                            "type": "string",
                            "enum": ["moving", "stationary"],
                            "description": "Simulation mode: 'moving' if traveling, 'stationary' if at destination."
                        }
                    }
                }
            }
        }
    }

    schema = {
        "type": "object",
        "required": ["planning_routine"],
        "additionalProperties": False,
        "properties": {
            "planning_routine": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema_routine
            }
        }
    }

    example = {
        "planning_routine": [{
            "morning_routine": ["Wake up at 7:00", "Drink water", "Exercise 20 mins", "Breakfast"],
            "evening_routine": ["Read book", "Journaling", "Sleep by 23:00"],
            "weekly_template": {
                "weekdays": "Work 9-6, Gym in evening",
                "weekends": "Hiking, Family time, Grocery shopping"
            },
            "habits": [
                {"name": "Gym", "frequency": "3 times/week", "time_of_day": "evening"},
                {"name": "Reading", "frequency": "daily", "time_of_day": "evening"}
            ],
            "circadian_rhythms": {
                "sleep_window": {"start_hour": 23, "end_hour": 7},
                "peak_productivity": {"start_hour": 10, "end_hour": 12},
                "social_window": {"start_hour": 18, "end_hour": 21},
                "energy_curve": [0.1, 0.1, 0.1, 0.1, 0.1, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0, 0.9, 0.7, 0.6, 0.7, 0.8, 0.7, 0.6, 0.7, 0.8, 0.6, 0.4, 0.3, 0.2]
            },
            "routine_anchors": [
                {"day": "Monday", "time": "09:00", "activity": "Team Sync", "location_type": "work", "mode": "stationary", "priority": 9, "duration_min": 60},
                {"day": "Friday", "time": "19:00", "activity": "Gym", "location_type": "public_place", "mode": "stationary", "priority": 7, "duration_min": 90},
                {"day": "Sunday", "time": "12:00", "activity": "Family Lunch", "location_type": "home", "mode": "stationary", "priority": 10, "duration_min": 120}
            ]
        }]
    }
    
    return system_instruction, example, schema


async def get_planning_day_schema(count, profile):
    # This was formerly get_planning_schema, now 'planning_day'
    type = "planning" 
    
    system_instruction_planning = f"""
        Ты - генератор распорядка дня агента (Part 3: Day Plan).
        Вход: Полный профиль (включая Strategy и Routine).
        Задача: на основе профиля сгенерировать полное расписание на СЕГОДНЯ.
        
        Возвращай массив событий внутри поля "planning_day".
        Генерируй полный распорядок дня (от пробуждения до сна).

        **КРИТИЧЕСКИ ВАЖНО - Используй данные из Profile["planning_routine"]:**
        - **circadian_rhythms.sleep_window**: Агент спит в это время - НЕ планируй активности.
        - **circadian_rhythms.peak_productivity**: Планируй важную работу сюда.
        - **circadian_rhythms.social_window**: Планируй встречи и общение сюда.
        - **circadian_rhythms.energy_curve**: Массив 24 чисел. Не планируй сложное в часы с низким значением.
        - **routine_anchors**: ОБЯЗАТЕЛЬНЫЕ события. Найди события с "day" = "{datetime.now(ZoneInfo('Asia/Almaty')).strftime('%A')}" и ВКЛЮЧИ их в расписание!
        
        **ЛОКАЦИИ И КООРДИНАТЫ:**
        - Если событие имеет `location_type` (например "work" или "restaurant"), ты ОБЯЗАН взять координаты из `profile.demographics.locations`.
        - Если это `location_type: "leisure"`, проверь `profile.demographics.locations.favorite_spots`.
        - Если места нет в профиле, генерируй реалистичные координаты в пределах города проживания агента.
        
        **НЕПРЕРЫВНОСТЬ ВРЕМЕНИ (TIMELINE CONTINUITY):**
        - Расписание должно быть непрерывным. `start_time` события N должно быть равно `end_time` события N-1.
        - Если между активностями нужно перемещение, создай отдельное событие с `activity_type: "commute"` и `mode: "moving"`.
        - **ОЦЕНКА ВРЕМЕНИ НА ДОРОГУ (Almaty context):**
            - Пешком < 1км: 10-15 мин.
            - На такси/машине по городу: 20-40 мин.
            - Час пик (08:00-10:00, 17:00-19:00): добавляй +20-30 мин.

        Правила:
        - Числовые значения в пределах логичных диапазонов.
        - Даты в формате YYYY-MM-DD либо ISO 8601 для временных меток.
        - Помни про приватность: помечай чувствительные элементы флагом `sensitive`.
        - Добавляй metadata.generated_on (ISO 8601) и metadata.confidence (0-1).
        - Включай параметры извлечения/забывания: forgetting_half_life_days, retention_score и salience для событий.
        - ИСПОЛЬЗУЙ ЛОКАЦИИ ИЗ profile.demographics.locations:
            1. День должен начинаться дома (координаты home).
            2. Если работает -> едет на работу (координаты work).
            3. Если учится -> едет в школу/университет (координаты school/university).
            4. Обед/вечер -> может посетить favorite_spot или вымышленные места РЯДОМ с работой/домом.
            5. Вечером возврат домой.
            6. Убедись, что origin текущего события совпадает с location предыдущего.
        - Если чего-то не хватает, делай реалистичные предположения и записывай их в metadata.inference_notes.
        
        * ECONOMY (`estimated_cost`):
            - Оценивай примерную стоимость события в KZT (тенге).
            - "Work", "Home", "Walking" -> 0.
            - "Lunch" -> 2000-5000, "Dinner" -> 5000-15000.
            - "Taxi" -> 1000-4000.
            
        * TRANSPORT (`transport_mode`):
            - Указывай явный способ передвижения: 'walking', 'transit' (bus/metro), 'taxi', 'car', 'bicycle'.
            - Если расстояние < 1км -> walking.
            
        * MIMORA SIMULATION (CRITICAL):
            - activity_type: ENUM ['sleep', 'personal_care', 'eating', 'work', 'commute', 'housework', 'leisure', 'social', 'shopping', 'education']
            - location_type: ENUM ['home', 'work', 'leisure', 'transit', 'outdoor', 'online', 'community', 'public_place', 'restaurant']
            - mode: ENUM ['moving', 'stationary'] (ОЧЕНЬ ВАЖНО: 'moving' если агент перемещается, 'stationary' если на месте)
            - is_socializing: true/false (если агент общается с кем-то)
            - expectation: Чего агент ожидает от этого действия (кратко)?
            - description: Детальное описание того, что именно делает агент (от 1-го лица).
            
        * SOCIAL (`with_whom`):
            - Указывай, с кем агент: ["Alone"], ["Colleagues"], ["Family"], ["Friend: Name"].
            
        profile (partially truncated for brevity):\n {json.dumps({k: v for k, v in profile.items() if k not in ["memories", "interactions", "large_metadata"]}, ensure_ascii=False)}
    """

    schema_planning = {
        "type": "object",
        "required": [
            "id", "title", "description", "expectation", "start_time", "end_time", 
            "activity_type", "location_type", "is_socializing", "origin", "location", 
            "transport_mode", "estimated_cost", "with_whom"
        ],
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string", "description": "Detailed description from 1st person."},
            "expectation": {"type": "string", "description": "What the agent expects to happen."},
            "start_time": {"type": "string", "format": "date-time"},
            "end_time": {"type": "string", "format": "date-time"},
            "activity_type": {
                "type": "string",
                "enum": ["sleep", "personal_care", "eating", "work", "commute", "housework", "leisure", "social", "shopping", "education"]
            },
            "location_type": {
                "type": "string",
                "enum": ["home", "work", "leisure", "transit", "outdoor", "online", "community", "public_place", "restaurant"]
            },
            "is_socializing": {"type": "boolean"},
            "origin": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "address": {"type": ["string", "null"]},
                    "lat": {"type": ["number", "null"]},
                    "lng": {"type": ["number", "null"]}
                },
                "required": ["lat", "lng"]
            },
            "location": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "address": {"type": ["string", "null"]},
                    "lat": {"type": ["number", "null"]},
                    "lng": {"type": ["number", "null"]}
                },
                "required": ["lat", "lng"]
            },
            "mode": {
                "type": "string",
                "enum": ["moving", "stationary"],
                "description": "Simulation mode: 'moving' if agent is traveling, 'stationary' if at a destination."
            },
            "transport_mode": {
                "type": "string",
                "enum": ["walking", "transit", "taxi", "car", "bicycle", "unknown", "stay"]
            },
            "estimated_cost": {
                "type": ["number", "null"],
                "minimum": 0,
                "description": "Estimated cost in KZT. Use 0 for stay/home/work. Use null only if absolutely unknown."
            },
            "speed_kmh": {"type": ["number", "null"], "minimum": 0},
            "with_whom": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of people or groups participating"
            },
            "repeat": {"type": ["string", "null"]},
            "metadata": {
                "type": "object",
                "properties": {
                    "generated_on": {"type": "string", "format": "date-time"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "inference_notes": {"type": "string"}
                }
            }
        }
    }

    schema = {
        "type": "object",
        "required": ["planning_day"],
        "additionalProperties": False,
        "properties": {
            "planning_day": {
                "type": "array",
                "minItems": 1,
                "maxItems": 50,
                "items": schema_planning
            },
            "metadata": {
                "type": "object"
            }
        }
    }

    example = {
        "planning_day": [{
            "id": "evt_1",
            "title": "Commute to Work",
            "description": "Я сажусь в машину и еду в офис, слушая утренний подкаст.",
            "expectation": "Доехать без пробок за 45 минут.",
            "start_time": f"{now_almaty[:10]}T08:00:00+05:00",
            "end_time": f"{now_almaty[:10]}T08:45:00+05:00",
            "activity_type": "commute",
            "location_type": "transit",
            "is_socializing": False,
            "origin": {"lat": 43.2, "lng": 76.8, "address": "Home"},
            "location": {"lat": 43.25, "lng": 76.9, "address": "Office Center"},
            "mode": "moving",
            "transport_mode": "car",
            "speed_kmh": 40,
            "estimated_cost": 0,
            "with_whom": ["Alone"],
            "repeat": "weekdays",
            "metadata": {"generated_on": now_almaty, "confidence": 1.0}
        },
        {
            "id": "evt_2",
            "title": "Lunch with Colleagues",
            "description": "Мы идём в соседнее кафе пообедать и обсудить планы на выходные.",
            "expectation": "Вкусно поесть и немного отвлечься от рабочих задач.",
            "start_time": f"{now_almaty[:10]}T13:00:00+05:00",
            "end_time": f"{now_almaty[:10]}T14:00:00+05:00",
            "activity_type": "eating",
            "location_type": "leisure",
            "is_socializing": True,
            "origin": {"lat": 43.25, "lng": 76.9, "address": "Office Center"},
            "location": {"lat": 43.255, "lng": 76.905, "address": "Local Cafe"},
            "mode": "stationary",
            "transport_mode": "walking",
            "speed_kmh": 5,
            "estimated_cost": 3500,
            "with_whom": ["Colleagues"],
            "repeat": "weekdays",
            "metadata": {"generated_on": now_almaty, "confidence": 0.9}
        }]
    }

    return system_instruction_planning, example, schema