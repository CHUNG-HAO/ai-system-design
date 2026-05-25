-- 1. 五類急重症案件數
SELECT
  suspected_condition AS 疑似病症,
  COUNT(*) AS 案件數
FROM ems_cases
GROUP BY suspected_condition
ORDER BY 案件數 DESC;

-- 2. P1 高優先案件清單
SELECT
  c.case_id AS 案件代碼,
  c.suspected_condition AS 疑似病症,
  c.priority AS 優先級,
  h.hospital_name AS 收治醫院,
  c.eta_time AS 預估到院時間,
  a.ack_minutes AS ACK分鐘數
FROM ems_cases c
JOIN hospitals h ON c.receiving_hospital_id = h.hospital_id
LEFT JOIN alerts a ON c.case_id = a.case_id
WHERE c.priority = 'P1'
ORDER BY c.eta_time
LIMIT 50;

-- 3. 各醫院平均 ACK 時間
SELECT
  h.hospital_name AS 醫院,
  ROUND(AVG(a.ack_minutes), 2) AS 平均ACK分鐘,
  COUNT(*) AS 通報數
FROM alerts a
JOIN hospitals h ON a.hospital_id = h.hospital_id
GROUP BY h.hospital_name
ORDER BY 平均ACK分鐘;

-- 4. 各病症流程達標率
SELECT
  c.suspected_condition AS 疑似病症,
  COUNT(*) AS 案件數,
  ROUND(AVG(o.protocol_target_met) * 100, 1) AS 達標率百分比
FROM ems_cases c
JOIN outcomes o ON c.case_id = o.case_id
GROUP BY c.suspected_condition
ORDER BY 達標率百分比 DESC;

-- 5. 到院前資源確認率
SELECT
  c.suspected_condition AS 疑似病症,
  COUNT(*) AS 資源需求數,
  ROUND(AVG(CASE WHEN ro.confirmed_time < c.arrival_hospital_time THEN 1.0 ELSE 0.0 END) * 100, 1) AS 到院前確認率百分比
FROM resource_orders ro
JOIN ems_cases c ON ro.case_id = c.case_id
GROUP BY c.suspected_condition
ORDER BY 到院前確認率百分比 DESC;

-- 6. 查單一案件完整摘要
SELECT
  c.case_id AS 案件代碼,
  p.age AS 年齡,
  p.sex AS 性別,
  c.suspected_condition AS 疑似病症,
  c.chief_complaint AS 主訴,
  c.initial_sbp AS 收縮壓,
  c.initial_hr AS 心跳,
  c.initial_spo2 AS 血氧,
  h.hospital_name AS 收治醫院,
  a.activation_type AS 啟動流程,
  a.ack_minutes AS ACK分鐘
FROM ems_cases c
JOIN patients p ON c.patient_id = p.patient_id
JOIN hospitals h ON c.receiving_hospital_id = h.hospital_id
LEFT JOIN alerts a ON c.case_id = a.case_id
WHERE c.case_id = 'E0000001';

-- 7. 查某案件生命徵象趨勢
SELECT
  v.sequence_no AS 順序,
  v.phase AS 階段,
  v.measured_at AS 量測時間,
  v.sbp AS 收縮壓,
  v.dbp AS 舒張壓,
  v.hr AS 心跳,
  v.rr AS 呼吸,
  v.spo2 AS 血氧,
  v.gcs AS GCS
FROM prehospital_vitals v
WHERE v.case_id = 'E0000001'
ORDER BY v.sequence_no;

-- 8. 推薦醫院 Top1 被採用比例
SELECT
  condition AS 病症,
  COUNT(*) AS 案件數,
  SUM(CASE WHEN selected_hospital_id = recommended_hospital_1 THEN 1 ELSE 0 END) AS 採用第一推薦數,
  ROUND(100.0 * SUM(CASE WHEN selected_hospital_id = recommended_hospital_1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS 第一推薦採用率百分比
FROM routing_recommendations
GROUP BY condition
ORDER BY 第一推薦採用率百分比 DESC;

-- 9. STEMI door-to-balloon 超過 90 分鐘案件
SELECT
  c.case_id AS 案件代碼,
  h.hospital_name AS 收治醫院,
  o.door_to_balloon_min AS DoorToBalloon分鐘,
  r.reason_1 AS 第一推薦原因,
  r.selected_reason AS 選擇原因
FROM ems_cases c
JOIN outcomes o ON c.case_id = o.case_id
JOIN hospitals h ON c.receiving_hospital_id = h.hospital_id
JOIN routing_recommendations r ON c.case_id = r.case_id
WHERE c.suspected_condition = 'STEMI'
  AND o.door_to_balloon_min > 90
ORDER BY o.door_to_balloon_min DESC;

-- 10. 找出快到院但資源尚未確認的案件
SELECT
  c.case_id AS 案件代碼,
  c.suspected_condition AS 疑似病症,
  h.hospital_name AS 收治醫院,
  ro.resource_type AS 尚未確認資源,
  c.arrival_hospital_time AS 到院時間,
  ro.request_status AS 資源狀態
FROM ems_cases c
JOIN hospitals h ON c.receiving_hospital_id = h.hospital_id
JOIN resource_orders ro ON c.case_id = ro.case_id
WHERE ro.request_status != 'confirmed'
ORDER BY c.arrival_hospital_time
LIMIT 50;
