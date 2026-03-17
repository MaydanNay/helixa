# app.services.schemas/editor.py

async def get_consistency_editor_schema(profile_full):
    type_name = "consistency_fix"
    system_instruction = f"""
        Ты - Главный Редактор ИИ-агентов. Твоя задача - проверить полный профиль агента на логические и хронологические противоречия и ИСПРАВИТЬ их.
        
        **ЧТО ПРОВЕРЯТЬ:**
        1. **Хронология**: Сравни дату рождения (birth) с датами в образовании (education), опыте работы (experience) и событиях памяти (history_events). 
           - Агент не может работать до рождения или закончить университет в 10 лет.
        2. **Социальная логика**: Если в демографии marital_status = "Single", у него не может быть "Wife" в известных агентах или биографии.
        3. **Психологическая связность**: Если Big5 Extraversion = 0.1 (интроверт), он не может быть "душой компании" в биографии или иметь social_window по 10 часов в день.
        4. **География**: В биографии не должно быть упоминания переезда в Париж, если все локации (home/work) находятся в Алматы.
        5. **Пространственная логика**: Проверь `planning_day`. Если расстояние между двумя последовательными точками (напр. Home и Work) велико, а время на перемещение слишком мало, увеличь время на перемещение.
        6. **Повествовательная связность (NARRATIVE COHERENCE)**: **ОЧЕНЬ ВАЖНО**. Проверь, как биография (`biography`) отражается в поведении (`behavioral`) и стиле речи (`voice`). 
           - Если в биографии была травма — она должна быть в `unresolved_tensions` или влиять на `temperament`.
           - Если агент — аристократ, его `voice_dna` не должен быть сленговым или грубым.
           - Если агент жил в бедности, это должно отражаться в `financial` (spending habits).
        
        **ТВОЯ ЗАДАЧА:**
        - Проанализировать входной JSON.
        - Сгенерировать ИСПРАВЛЕННУЮ версию полей, где найдены ошибки.
        - Если ошибок нет, верни поля без изменений.
        
        Верни JSON объект, содержащий ПОЛНЫЙ исправленный профиль в том же формате, что и на входе.
    """

    # We don't define a static schema here because the input is the entire complex agent_data
    # We will use the same schema as the input to ensure valid output.
    # For transparency, we can use a wrapper if needed, but usually we want the full object back.
    
    return system_instruction, {}, None # Schema will be handled by ensure_schema_valid or passed as None if we want raw reconstruction
