# AgentDojo IFC Global Tool Contract 语义审查报告（GPT-5.5）

## 1. 结论

原始 `agentdojo_ifc_global_tool_contract_draft.json` 的结构已经符合 IFC-aligned 合约初稿要求，但代码启发式生成的语义分配仍存在明显偏差，尤其是将大量内容参数误判为 `target`，以及将若干只读工具误判为 `ACTION`。本次语义审查在不改变核心枚举和 JSON 总体结构的前提下，生成了 `agentdojo_ifc_global_tool_contract_semantic_review_gpt55.json`。

## 2. 统计对比

### 2.1 Tool Type

| 类型 | 原始 draft | GPT-5.5 语义审查版 |
|---|---:|---:|
| ACTION | 32 | 24 |
| READ_LOW | 16 | 20 |
| READ_SENSITIVE | 21 | 25 |

### 2.2 Sink Scope

| Scope | 原始 draft | GPT-5.5 语义审查版 |
|---|---:|---:|
| booking | 0 | 3 |
| calendar | 2 | 6 |
| credential | 1 | 1 |
| external | 1 | 4 |
| financial | 7 | 7 |
| internal | 0 | 3 |
| messaging | 22 | 13 |
| none | 27 | 23 |
| public | 1 | 1 |
| workspace | 8 | 8 |

### 2.3 参数角色

| sink_role | 原始 draft | GPT-5.5 语义审查版 |
|---|---:|---:|
| command | 2 | 0 |
| content | 3 | 16 |
| control | 18 | 21 |
| credential | 1 | 1 |
| selector | 11 | 39 |
| target | 67 | 25 |

参数总数保持不变：102 → 102。

## 3. 主要修正

### 3.1 Tool Type 修正

以下只读工具从 `ACTION` 调整为 `READ_SENSITIVE` 或 `READ_LOW`：

| 工具 | 原始 | 调整后 |
|---|---|---|
| `get_car_rental_address` | `ACTION` | `READ_LOW` |
| `get_contact_information_for_restaurants` | `READ_SENSITIVE` | `READ_LOW` |
| `get_hotels_address` | `ACTION` | `READ_LOW` |
| `get_received_emails` | `ACTION` | `READ_SENSITIVE` |
| `get_restaurants_address` | `ACTION` | `READ_LOW` |
| `get_scheduled_transactions` | `ACTION` | `READ_SENSITIVE` |
| `get_unread_emails` | `ACTION` | `READ_SENSITIVE` |
| `get_user_information` | `ACTION` | `READ_SENSITIVE` |
| `search_emails` | `ACTION` | `READ_SENSITIVE` |

### 3.2 Sink Scope 修正

将 Calendar、Booking、User Info 等工具从过粗的 `messaging/none` 调整到更准确的 scope：

| 工具 | 原始 | 调整后 |
|---|---|---|
| `add_calendar_event_participants` | `messaging` | `calendar` |
| `add_user_to_channel` | `messaging` | `external` |
| `cancel_calendar_event` | `messaging` | `calendar` |
| `create_calendar_event` | `messaging` | `calendar` |
| `get_user_info` | `none` | `internal` |
| `get_user_information` | `messaging` | `internal` |
| `invite_user_to_slack` | `messaging` | `external` |
| `remove_user_from_slack` | `messaging` | `external` |
| `reschedule_calendar_event` | `messaging` | `calendar` |
| `reserve_car_rental` | `none` | `booking` |
| `reserve_hotel` | `none` | `booking` |
| `reserve_restaurant` | `none` | `booking` |
| `search_contacts_by_email` | `messaging` | `none` |
| `update_user_info` | `none` | `internal` |

### 3.3 参数角色修正

重点修正内容参数、对象选择参数和时间/金额控制参数：

| 工具参数 | 原始 role | 调整后 role |
|---|---|---|
| `add_calendar_event_participants.event_id` | `target` | `selector` |
| `append_to_file.content` | `target` | `content` |
| `append_to_file.file_id` | `target` | `selector` |
| `cancel_calendar_event.event_id` | `target` | `selector` |
| `check_restaurant_opening_hours.restaurant_names` | `target` | `selector` |
| `create_calendar_event.description` | `command` | `content` |
| `create_calendar_event.title` | `selector` | `content` |
| `create_file.content` | `target` | `content` |
| `create_file.filename` | `target` | `selector` |
| `delete_email.email_id` | `target` | `selector` |
| `delete_file.file_id` | `target` | `selector` |
| `get_all_car_rental_companies_in_city.city` | `target` | `selector` |
| `get_all_hotels_in_city.city` | `target` | `selector` |
| `get_all_restaurants_in_city.city` | `target` | `selector` |
| `get_car_fuel_options.company_name` | `target` | `selector` |
| `get_car_price_per_day.company_name` | `target` | `selector` |
| `get_car_rental_address.company_name` | `target` | `selector` |
| `get_car_types_available.company_name` | `target` | `selector` |
| `get_contact_information_for_restaurants.restaurant_names` | `target` | `selector` |
| `get_cuisine_type_for_restaurants.restaurant_names` | `target` | `selector` |
| `get_day_calendar_events.day` | `target` | `control` |
| `get_dietary_restrictions_for_all_restaurants.restaurant_names` | `target` | `selector` |
| `get_file_by_id.file_id` | `target` | `selector` |
| `get_flight_information.arrival_city` | `target` | `selector` |
| `get_flight_information.departure_city` | `target` | `selector` |
| `get_hotels_address.hotel_name` | `target` | `selector` |
| `get_hotels_prices.hotel_names` | `target` | `selector` |
| `get_most_recent_transactions.n` | `target` | `control` |
| `get_price_for_restaurants.restaurant_names` | `target` | `selector` |
| `get_rating_reviews_for_car_rental.company_name` | `target` | `selector` |
| `get_rating_reviews_for_hotels.hotel_names` | `target` | `selector` |
| `get_rating_reviews_for_restaurants.restaurant_names` | `target` | `selector` |
| `get_restaurants_address.restaurant_names` | `target` | `selector` |
| `post_webpage.content` | `selector` | `content` |
| `read_file.file_path` | `target` | `selector` |
| `reschedule_calendar_event.event_id` | `target` | `selector` |
| `reserve_car_rental.company` | `selector` | `target` |
| `reserve_hotel.end_day` | `selector` | `control` |
| `reserve_hotel.hotel` | `selector` | `target` |
| `reserve_hotel.start_day` | `selector` | `control` |
| `reserve_restaurant.restaurant` | `selector` | `target` |
| `schedule_transaction.subject` | `selector` | `content` |
| `search_calendar_events.query` | `command` | `selector` |
| `search_contacts_by_email.query` | `target` | `selector` |
| `search_contacts_by_name.query` | `target` | `selector` |
| `search_emails.query` | `target` | `selector` |
| `search_files.query` | `target` | `selector` |
| `search_files_by_filename.filename` | `target` | `selector` |
| `send_email.attachments` | `control` | `selector` |
| `send_email.body` | `target` | `content` |
| `send_email.subject` | `target` | `content` |
| `share_file.file_id` | `target` | `selector` |
| `update_scheduled_transaction.subject` | `selector` | `content` |
| `update_user_info.city` | `target` | `content` |
| `update_user_info.first_name` | `target` | `content` |
| `update_user_info.last_name` | `target` | `content` |
| `update_user_info.street` | `target` | `content` |

## 4. 关键语义规则

- `content/body/message/subject/description/title/note/summary` 优先作为 `content`，而不是 `target` 或 `command`。

- `file_id/email_id/event_id/id/query/filename/city/company_name` 主要作为 `selector`，除非它直接表示外部接收者或通信目标。

- `recipient/channel/user/email/participants` 作为 `target`，因为它们决定动作目的地或外部主体。

- `amount/date/start_time/end_time/recurring/permission` 作为 `control`。

- `get_/search_/read_/list_/check_` 工具默认不是 `ACTION`，除非工具名明确表达状态变更。

- Calendar 工具以 `calendar` 为主 scope，不因为 schema 描述中提到邮件通知就归为 `messaging`。

- `reserve_hotel/reserve_restaurant/reserve_car_rental` 使用 `booking` scope，便于后续与 Travel/τ-bench 类 benchmark 对齐。

- `read_file/get_file_by_id/get_webpage/read_channel_messages/email-like read` 的自然语言输出设置为低完整性或需要结构化抽取，以避免外部文本直接控制 action 参数。


## 5. 仍需人工确认的点

- `selector` 和 `target` 在对象 ID 上仍有边界问题，例如 `event_id/file_id/email_id`。当前语义审查倾向将它们作为 `selector`，并通过 `object_confidentiality_check/source_object_binding` 强化对象级约束。

- `C_max` 当前作为合约字段保留，建议第一阶段只对外发/共享/公开发布类 sink 强执行，Workspace 内部写入不应强制公开级别保密约束。

- 该文件仍是“冻结候选版”，不是最终 runtime 合约。接入 runtime 前需要在 Banking、Slack、Workspace、Calendar、Travel 各挑 2–3 个高风险工具做 case-level 验证。


## 6. 输出文件

- `agentdojo_ifc_global_tool_contract_semantic_review_gpt55.json`

- `agentdojo_ifc_global_tool_contract_semantic_review_pack_gpt55.json`
