"""阻止模型引用不存在的来源或声明未使用的引用。"""

from __future__ import annotations

import re

from ..errors import CitationError
from ..models import RegisteredSource
from .ledger import EvidenceLedger

_INLINE_CITATION = re.compile(r"\[(S\d+)\]")


class CitationValidator:
    def validate(
        self,
        answer: str,
        citation_ids: list[str],
        ledger: EvidenceLedger,
    ) -> tuple[RegisteredSource, ...]:
        if not answer.strip():
            raise CitationError("最终答案不能为空")
        declared = list(dict.fromkeys(citation_ids))
        inline = list(dict.fromkeys(_INLINE_CITATION.findall(answer)))
        unknown = [source_id for source_id in declared + inline if ledger.get(source_id) is None]
        if unknown:
            raise CitationError(f"引用了不存在的来源：{', '.join(dict.fromkeys(unknown))}")
        if ledger.all() and not declared:
            raise CitationError("已有检索证据，但最终答案没有 citations")
        if set(declared) != set(inline):
            raise CitationError("answer 中的 [Sx] 标记必须与 citations 列表完全一致")
        sources: list[RegisteredSource] = []
        for source_id in declared:
            source = ledger.get(source_id)
            if source is not None:
                sources.append(source)
        return tuple(sources)
