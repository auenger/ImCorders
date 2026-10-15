# 产品返厂以后怎样接回制造履历

作者：杨正武
来源：https://imcoders.cn/manufacturing/returned-product-manufacturing-history/
发布：2026-10-15T00:00:00.000Z
更新：2026-10-15T00:00:00.000Z

沿客户报修、返厂授权、实收检验、维修换件和重新交付，建立序列号与在役配置的证据链，核对部分到货、报废、质保与工程变更边界，附可复算的返厂处置样本。

---


客户报修十台设备，仓库只收到八台。服务单里写着“维修完成”，其中两台其实已经批准报废。若系统把返厂授权数当成实收数，再把维修状态写回原始出厂履历，库存、服务和质量记录都会失去对应关系。

本篇完成 S07，用独立模拟案例 `RMA-S01` 连接[服务支撑专题](/manufacturing/people-documents-service-operations/)与[质量影响分析](/manufacturing/quality-incident-traceability-scope/)。数量、序列号和判定条件均为教学设定，不涉及真实客户或实际质量事故。

## 报修、授权与实收分别登记

客户案例 `CASE-S01` 报告十台风机有异常噪声，序列号 `SN01` 至 `SN10`。服务人员建立返厂授权，但这一步只说明允许退回哪些对象，不能证明物流已完成或企业已承担质量责任。

Dynamics 365 Field Service 将 RMA 与 RMA receipt 分为不同记录。[返厂处理文档](https://learn.microsoft.com/en-us/dynamics365/field-service/process-return)提供产品实现例子。本篇的逐件身份、检验条件和处置审批是额外定义的案例规则。

| 记录 | 样本内容 | 对应状态 |
| --- | --- | --- |
| CASE-S01 | SN01—SN10 报告异常噪声 | 客户现象，原因待查 |
| RMA-S01 | 授权退回十台 | 等待实收 |
| RCPT-S01 | 实收 SN01—SN08 | 八台进入隔离检验 |
| OPEN-S01 | SN09、SN10 未收到 | 继续追踪，不能登记维修完成 |

收货时扫描序列号，保存客户、所有权、物流包裹、附件和外观记录。退回对象与原出厂产品身份不符时，建立待核实项；不得用相近型号随意匹配。客户所有物也不应在没有依据时转成企业可销售库存。

## 检验结果连接原始制造证据

按序列号查询出厂结构、装配记录、检测与放行版本，再检查历次服务更换。出厂配置保存当时事实，当前在役配置按每次变动的生效时间更新，二者可并存。

本样本检验 `INSP-S01` 覆盖八台实收对象。SN01—SN06 的指定支架发现裂纹，批准更换；SN07、SN08 按模拟的经济性与技术评估批准报废。这里的裂纹是检验现象，根因保持未确认，不能据此写成“设计缺陷导致全部产品故障”。

制造谱系若指向同一供应批次，还需要核对其他使用对象。缺少历史部件身份时，应列出未知范围。[质量影响分析](/manufacturing/quality-incident-traceability-scope/)提供正反向追踪方法；本篇仅完成这十个序列号的服务案例，不据此声明召回范围已经确定。

<figure class="archify-embed">
<div class="archify-embed-heading"><strong>客户报修怎样接到实收与原始履历</strong><a href="/manufacturing/maps/service-return-evidence.html" target="_blank" rel="noopener noreferrer">独立窗口查看 ↗</a></div>
<iframe src="/manufacturing/maps/service-return-evidence.html" title="客户报修与返厂授权经实际收货关联制造履历和检验的数据流" loading="lazy" allowfullscreen></iframe>
<figcaption>授权数量、实收身份和检验对象分别核对，未收到的两个序列号保持未决。</figcaption>
</figure>

## 维修换件保留拆下与装上的关系

维修工单 `WO-S01` 对六台分别记录旧支架 P01—P06、新支架 N01—N06、拆装时间、人员及作业文件版本。每对关系都绑定具体序列号。新件由获准的批次领用，拆下件进入单独的保留或处置状态，不能自动回到良品库存。

维修后按本案例批准的测试方案形成六条测试记录，全部合格后再批准重新交付。测试要求与阈值应来自适用产品依据；本文不编造通用的振动值或噪声限值。若一次测试失败，保留该尝试及后续重测，不能覆盖成只有一次成功。

Dynamics 365 的销售退回说明将到货、检验、处置以及替换订单联系起来，具体结果取决于配置和处置代码。[销售退回文档](https://learn.microsoft.com/en-us/dynamics365/supply-chain/sales-marketing/sales-returns)说明的是产品流程，不能代替合同、质保与质量批准。

```text
授权返厂 10 = 实收 8 + 未收到 2
实收处置 8 = 维修后交付 6 + 批准报废 2
实际新件使用 6 = 六条产品换件关系各 1
本次重新交付身份 = SN01—SN06
```

SN07、SN08 的报废批准、实际执行和库存结果分别留痕，本样本预期三者完成。是否退款、赔偿或开具红字单据，由合同和财务流程另行处理。服务关闭、物理处置和账务结算各有截止条件，不能用一个“已结束”代表全部完成。

## 服务反馈进入质量与工程评估

六个裂纹观测可以进入质量问题记录 `QI-S01`，附照片、位置、使用条件与制造来源。质量人员确定调查范围，工程人员建立变更提议 `ECR-S01`。提议阶段保留假设及待验证内容，不能自动更改 BOM 或追认新设计已获批准。

若工程变更最终批准，应记录验证、适用序列号或批次、服务改装方案及完成回执。新版本是否适用于已经交付的产品，需要明确决定；后续出厂产品和现场在役产品不能仅靠“最新版本”统一覆盖。

<figure class="archify-embed">
<div class="archify-embed-heading"><strong>返厂处置怎样形成配置和改进记录</strong><a href="/manufacturing/maps/service-disposition-change.html" target="_blank" rel="noopener noreferrer">独立窗口查看 ↗</a></div>
<iframe src="/manufacturing/maps/service-disposition-change.html" title="检验结果经批准维修或报废并形成在役配置与工程评估的数据流" loading="lazy" allowfullscreen></iframe>
<figcaption>重新交付需要维修、测试和放行依据；质量反馈可以发起工程评估，工程发布仍需独立批准。</figcaption>
</figure>

## 按身份集合验收返厂闭环

[返厂样本 JSON](/manufacturing/samples/service-return.json)保留授权、实收、未到、维修、报废和重新交付集合，并逐台记录换件。[校验程序](/manufacturing/samples/verify-completion-samples.py)验证集合不重叠、数量守恒及六条新旧件映射，不能证明真实测试已经执行。

| 依据 | 可以支持的内容 | 适用限制 |
| --- | --- | --- |
| Field Service RMA 文档 | 授权退回与实收分别建档 | 具体检验和身份规则需要配置 |
| Supply Chain 销售退回文档 | 检验、处置与替换流程关系 | 不覆盖所有合同及财务要求 |
| 本篇 JSON | 十个序列号的去向与换件复算 | 全部为教学数据 |

网页于 2026-10-15 核对。实际验收还要逐项查看收货、检验、拆装、测试、放行与报废回执，以及仍未收到的两台如何继续跟踪。根因和工程提议可以保持开放，文章不会把它们写成已经完成的改进结果。
