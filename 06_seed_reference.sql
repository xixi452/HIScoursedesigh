INSERT OR IGNORE INTO roles (role_id, role_code, role_name) VALUES
(1, 'admin', '管理员'),
(2, 'registrar', '挂号员'),
(3, 'doctor', '医生'),
(4, 'cashier', '收费员'),
(5, 'pharmacist', '药师');

INSERT OR IGNORE INTO permissions (permission_id, permission_code, permission_name) VALUES
(1, 'patient:create', '患者建档'),
(2, 'patient:read', '查看患者'),
(3, 'schedule:manage', '排班号源维护'),
(4, 'schedule:read', '号源查询'),
(5, 'reg:create', '挂号'),
(6, 'reg:cancel', '退号'),
(7, 'reg:read', '挂号查询'),
(8, 'encounter:update', '接诊与病历'),
(9, 'prescription:create', '开方'),
(10, 'prescription:update', '处方修改与作废'),
(11, 'prescription:read', '查看处方'),
(12, 'billing:charge', '收费'),
(13, 'billing:refund', '退费'),
(14, 'billing:read', '收费查询'),
(15, 'pharmacy:dispense', '发药'),
(16, 'pharmacy:return', '退药'),
(17, 'pharmacy:stock_in', '药品入库'),
(18, 'pharmacy:stock_read', '库存查询'),
(19, 'report:read', '报表查询'),
(20, 'admin:user', '用户管理'),
(21, 'admin:role', '角色权限管理'),
(22, 'admin:masterdata', '基础数据维护'),
(23, 'admin:audit', '审计日志');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES
(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8),
(1, 9), (1, 10), (1, 11), (1, 12), (1, 13), (1, 14), (1, 15), (1, 16),
(1, 17), (1, 18), (1, 19), (1, 20), (1, 21), (1, 22), (1, 23),
(2, 1), (2, 2), (2, 4), (2, 5), (2, 6), (2, 7), (2, 19),
(3, 2), (3, 7), (3, 8), (3, 9), (3, 10), (3, 11), (3, 19),
(4, 2), (4, 11), (4, 12), (4, 13), (4, 14), (4, 19),
(5, 2), (5, 11), (5, 15), (5, 16), (5, 17), (5, 18), (5, 19);
