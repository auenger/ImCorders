# 药品批记录怎样支持复核与放行

作者：杨正武
来源：https://imcoders.cn/manufacturing/pharma-batch-review-release/
发布：2026-10-15T00:00:00.000Z
更新：2026-10-15T00:00:00.000Z

以美国药品 CGMP 公开条文为依据，拆解主批记录、执行证据、实验室结果、偏差调查与质量复核的关系，用包装数量样本说明记录齐全和获准放行的区别，并限定法规适用范围。

---


批记录每个字段都有值，实验室结果也显示通过，批次仍可能无法放行。一条尚未调查清楚的偏差、错误的标签版本，或无法回查的原始数据，都会让“完成率百分之百”失去实际意义。

本篇展开 I05 的药品生产部分，依据美国 21 CFR Part 211 的公开条文讨论记录关系。它不覆盖医疗器械专属法规、中国药品 GMP、欧盟 GMP 或所有药品剂型，也不构成对具体工厂的合规认定。所有批次和数量均为教学模拟。

## 从适用条文确定需要回查的对象

[21 CFR 211.188](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-C/part-211/subpart-J/section-211.188)要求为所生产的每批药品准备批生产及控制记录，并列出设备、组件批次、用量、过程及实验室控制、产率、人员与调查等记录内容。软件表单可据此建立检查项，但具体字段和实施方式需要结合工艺及适用要求。

[21 CFR 211.192](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-C/part-211/subpart-J/section-211.192)涉及质量控制部门在放行或分销前对生产控制记录的复核批准，并要求调查无法解释的差异或不符合规格等情况。仅有某个检验结果通过，不能代替这一复核过程。

| 对象 | 本例如何建立关联 | 需要回查的证据 |
| --- | --- | --- |
| 主批记录 | MASTER-P / 3 | 适用产品、工艺、批准版本 |
| 执行批记录 | BATCH-P01 | 所采用版本与实际步骤 |
| 物料与设备 | 来源批号、设备身份 | 状态、用量、时间及执行记录 |
| 样品与检验 | SAMPLE-P01、TEST-P01 | 方法版本、原始数据与复核 |
| 偏差调查 | DEV-P01 | 事实、影响评估、结论与批准 |
| 放行决定 | RELEASE-P01 | 复核范围、决定及有权人员 |

这些示例字段由本文设计，法规要求仍以对应原文为依据。引用条文只能支持其实际覆盖的要求，不能据此声称电子签名、系统验证或无菌生产要求也已全部满足。

## 执行记录保持版本和原始依据

执行批次引用获准主记录，记录实际时间、操作者、所用组件、设备和过程结果。偏离预定步骤时保留原记录、变更原因与调查关联，不能在完成后把原始值改成计划值。

FDA 的[数据完整性最终指南](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/data-integrity-and-compliance-drug-cgmp-questions-and-answers)说明药品 CGMP 下的数据完整性关注，并讨论基于过程理解和风险的管理。指南与法规的性质不同；本篇用它说明资料背景，不把指南标题当成系统认证。

电子记录需要能回查元数据、变更与审核。纸面签字扫描件也要有原始来源和适用关系，不能把上传附件自动视为原始电子数据完整保留。具体电子记录和签名要求需要另行确认适用制度及系统设计，本篇不虚构签名有效性结论。

<figure class="archify-embed">
<div class="archify-embed-heading"><strong>主批记录怎样连接实际执行与检验</strong><a href="/manufacturing/maps/pharma-execution-evidence.html" target="_blank" rel="noopener noreferrer">独立窗口查看 ↗</a></div>
<iframe src="/manufacturing/maps/pharma-execution-evidence.html" title="主批记录版本关联物料设备执行与实验室结果形成复核资料的数据流" loading="lazy" allowfullscreen></iframe>
<figcaption>图示为记录关联模型，未实现验证过的电子批记录系统，也不证明法规符合性。</figcaption>
</figure>

## 包装数量对平以后仍要解释偏差

本例只复算包装工段，假定进入包装的合格中间产品足以形成 10,000 瓶理论数量。实际取得 9,800 瓶完整包装，其中 100 瓶作为留样、9,700 瓶进入待放行库存；另有相当于 200 瓶的损失记录。所有数量和百分比均为教学设定。

```text
理论数量10000 = 完整包装9800 + 损失200
完整包装9800 = 待放行库存9700 + 留样100
完整包装产率 = 9800 / 10000 = 98%
```

98% 的算术结果不能独立证明产率可接受。实际允许范围应来自适用的获准记录和工艺依据。包装物料、标签领退、销毁、线清场与其他必要项目还需分别核对，不能因瓶数相等就自动关闭整批。

样本另设 DEV-P01 为一条尚待完成调查的过程差异。实验室结果 TEST-P01 通过，但偏差状态仍为开放，因此 RELEASE-P01 保持待复核，9,700 瓶不能被界面标记为“已放行”。本文没有编造该偏差的临床风险或根因。

## 调查、复核和目标状态形成独立回执

偏差调查需要能查看事实、相关数据、影响对象、结论及后续行动。是否涉及其他批次，按调查证据核对。修正一个界面值不能替代调查，也不能删除原始超限或异常记录。

本样本的复核条件包含执行资料、实验室复核、数量核对及偏差处理状态。只有授权决定形成后，才向目标库存提出相应状态应用；目标回执说明实际生效对象和范围。决定记录、目标限制解除和实际发运分别保存。

<figure class="archify-embed">
<div class="archify-embed-heading"><strong>偏差和记录复核怎样约束批次放行</strong><a href="/manufacturing/maps/pharma-review-release.html" target="_blank" rel="noopener noreferrer">独立窗口查看 ↗</a></div>
<iframe src="/manufacturing/maps/pharma-review-release.html" title="批记录检验偏差与数量核对经质量复核后形成放行决定和库存回执的数据流" loading="lazy" allowfullscreen></iframe>
<figcaption>本例偏差开放，复核保持未通过。图中的批准路径描述满足条件时的流程，不表示本批已获准放行。</figcaption>
</figure>

## 来源与样本分别验收

[药品批记录 JSON](/manufacturing/samples/pharma-batch.json)保存包装数量和复核条件；[校验程序](/manufacturing/samples/verify-completion-samples.py)复算数量，并验证开放偏差阻止本例放行。程序只体现样本规则，不执行真实质量决策。

| 依据 | 支持内容 | 范围 |
| --- | --- | --- |
| 21 CFR 211.188 | 药品批生产控制记录的相关内容 | 美国相应药品 CGMP 条文 |
| 21 CFR 211.192 | 生产记录复核与差异调查 | 不代表所有地区法规 |
| FDA 2018 最终指南 | 药品 CGMP 数据完整性背景 | 指南不提供认证结论 |
| 本篇 JSON | 包装数量与待放行状态复算 | 阈值、工艺和验证均非实测 |

上述网页于 2026-10-15 核对。实际项目需要适用法规清单、获准工艺、验证材料和完整质量程序；本篇保留的数据模型不能据此直接用于药品放行。
