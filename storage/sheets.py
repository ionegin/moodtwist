import gspread
from config import CREDENTIALS_FILE, GOOGLE_SHEET_ID
from datetime import datetime
from metrics import is_metric_summable, get_measurement_config

class GoogleSheetsStorage:
    def __init__(self):
        self.gc = gspread.service_account(filename=CREDENTIALS_FILE)
        self.sh = self.gc.open_by_key(GOOGLE_SHEET_ID)

    def check_today_metric(self, user_id, metric_key, logical_date):
        try:
            worksheet = self.sh.get_worksheet(0)
            all_values = worksheet.get_all_values()
            if not all_values:
                return None

            headers = [h.strip() for h in all_values[0]]
            try:
                date_idx = headers.index("Date")
                metric_idx = headers.index(metric_key)
            except ValueError:
                return None

            matching_values = []
            for row in all_values[1:]:
                if len(row) <= max(date_idx, metric_idx):
                    continue
                if row[date_idx].strip() == logical_date:
                    val = row[metric_idx].strip()
                    if val:
                        matching_values.append(val)

            if not matching_values:
                return None

            if is_metric_summable(metric_key):
                total = 0.0
                for v in matching_values:
                    try:
                        total += float(v.replace(',', '.'))
                    except ValueError:
                        continue
                return total if total > 0 else None

            return matching_values[-1]

        except Exception as e:
            print(f"[SHEETS] Error in check_today_metric: {e}")
            return None

    def get_day_data(self, user_id, logical_date):
        """Возвращает все метрики за день одним запросом, суммируя числовые."""
        try:
            worksheet = self.sh.get_worksheet(0)
            all_values = worksheet.get_all_values()
            if not all_values:
                return {}

            headers = [h.strip() for h in all_values[0]]
            try:
                date_idx = headers.index("Date")
            except ValueError:
                return {}

            raw = {}
            for row in all_values[1:]:
                if len(row) <= date_idx:
                    continue
                if row[date_idx].strip() == logical_date:
                    for i, val in enumerate(row):
                        if i < len(headers) and val.strip():
                            key = headers[i]
                            if key not in raw:
                                raw[key] = []
                            raw[key].append(val.strip())

            result = {}
            for key, values in raw.items():
                if is_metric_summable(key):
                    total = 0.0
                    for v in values:
                        try:
                            total += float(v.replace(',', '.'))
                        except ValueError:
                            continue
                    if total > 0:
                        result[key] = str(total)
                elif get_measurement_config(key).get("format") == "yes_no":
                    # Для yes_no логика: берем самое первое значение за день
                    result[key] = values[0]
                else:
                    result[key] = values[-1]

            return result

        except Exception as e:
            print(f"[SHEETS] Error in get_day_data: {e}")
            return {}

    def update_first_row_yesno(self, user_id, logical_date, metric_key, value):
        """Обновляет yes-no значение в первой строке за день."""
        try:
            worksheet = self.sh.get_worksheet(0)
            all_values = worksheet.get_all_values()
            if not all_values:
                return False

            headers = [h.strip() for h in all_values[0]]
            try:
                date_idx = headers.index("Date")
                metric_idx = headers.index(metric_key)
            except ValueError:
                print(f"[SHEETS] update_first_row_yesno: column '{metric_key}' not found")
                return False

            for row_num, row in enumerate(all_values[1:], start=2):
                if len(row) <= date_idx:
                    continue
                if row[date_idx].strip() == logical_date:
                    worksheet.update_cell(row_num, metric_idx + 1, value)
                    print(f"[SHEETS] updated {metric_key}={value} at row {row_num}")
                    return True

            print(f"[SHEETS] update_first_row_yesno: no row found for date={logical_date}. Creating new row.")
            local_now = datetime.now()
            # If no row exists, we append a new one
            self.save_daily(user_id, {
                "Date": logical_date,
                "created_at": str(local_now.strftime("%Y-%m-%d %H:%M")),
                metric_key: value
            })
            return True

        except Exception as e:
            print(f"[SHEETS] Error in update_first_row_yesno: {e}")
            import traceback
            traceback.print_exc()
            return False

    def save_daily(self, user_id, data):
        try:
            worksheet = self.sh.get_worksheet(0)
            headers = [h.strip() for h in worksheet.row_values(1)]

            new_keys = [k for k in data if k not in headers]
            if new_keys:
                print(f"[SHEETS] adding new columns: {new_keys}")
                for key in new_keys:
                    headers.append(key)
                    worksheet.update_cell(1, len(headers), key)

            print(f"[SHEETS] headers={headers}")

            row_to_append = [
                "" if data.get(h) is None else str(data.get(h, ""))
                for h in headers
            ]

            print(f"[SHEETS] row_to_append={row_to_append}")
            worksheet.append_row(row_to_append, value_input_option='USER_ENTERED')
            print(f"[SHEETS] append_row OK")

        except Exception as e:
            print(f"[SHEETS] ERROR in save_daily: {e}")
            import traceback
            traceback.print_exc()

    def save_note(self, user_id, text, is_voice=False, duration=None, telegram_ts=None, uploaded_at=None, source="manual", created_at_override=None):
        try:
            try:
                worksheet = self.sh.worksheet("Notes")
            except Exception:
                worksheet = self.sh.add_worksheet(title="Notes", rows="100", cols="20")
                # Создаем лист с новыми заголовками, если не было
                worksheet.append_row(["created_at", "source", "note", "duration", "ai_score"])

            from datetime import timedelta
            if created_at_override:
                created_str = created_at_override
            elif telegram_ts:
                created_str = str((telegram_ts + timedelta(hours=2)).strftime("%Y-%m-%d"))
            else:
                created_str = str(datetime.now().strftime("%Y-%m-%d"))

            source_val = source if source != "manual" else ("voice_note" if is_voice else "text_note")
            
            data = {
                "created_at": created_str,
                "source": source_val,
                "note": text,
                "duration": duration if duration else 0,
                "ai_score": ""
            }

            headers = [h.strip() for h in worksheet.row_values(1)]
            if not headers:
                headers = ["created_at", "source", "note", "duration", "ai_score"]
                worksheet.append_row(headers)
            elif "format" in headers and "source" not in headers:
                # Переименовываем старую колонку format в source
                idx = headers.index("format")
                headers[idx] = "source"
                worksheet.update_cell(1, idx + 1, "source")
                
            new_keys = [k for k in data if k not in headers]
            if new_keys:
                print(f"[SHEETS] adding new columns to Notes: {new_keys}")
                for key in new_keys:
                    headers.append(key)
                    worksheet.update_cell(1, len(headers), key)

            row_to_append = [str(data.get(h, "")) for h in headers]

            worksheet.append_row(row_to_append, value_input_option='USER_ENTERED')
            print(f"[SHEETS] note saved OK")

        except Exception as e:
            print(f"[SHEETS] Error saving note: {e}")
            import traceback
            traceback.print_exc()
