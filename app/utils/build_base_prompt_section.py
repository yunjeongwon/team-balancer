def build_base_prompt_section(
    formatted_score_groups: str,
    formatted_must_link_groups: str,
    formatted_cannot_link_groups: str,
) -> str:
    return f"""
### 입력

formatted_score_groups:
{formatted_score_groups}

- 형식: 점수별 그룹 문자열
- 각 줄 형식: "<점수>: 이름1, 이름2, ..."
- 높은 점수부터 정렬됨
- 같은 점수의 멤버들은 동일 줄에 그룹화됨

formatted_must_link_groups:
{formatted_must_link_groups}

- 같은 줄의 멤버들은 반드시 같은 팀이어야 함
- 각 줄은 하나의 묶음 그룹 의미

formatted_cannot_link_groups:
{formatted_cannot_link_groups}

- 같은 줄의 멤버들은 반드시 같은 팀이어야 함
- 각 줄은 하나의 분리 그룹 의미

---

### 핵심 목표

두 팀을 구성할 때 다음을 모두 만족해야 합니다:

1. **가중치 분포 균형 유지 (최우선)**
2. **총 가중치 합 차이 최소화**
3. **formatted_must_link_groups 반드시 만족**
4. **formatted_cannot_link_groups 반드시 만족**
5. **(피드백 존재 시) 개선된 결과 생성**

---

### 핵심 로직 (반드시 준수)

#### 1. 그룹 제약 우선 처리
- formatted_must_link_groups:
  - 각 그룹을 하나의 “묶음 단위(super node)”로 취급하여 분배
- formatted_cannot_link_groups:
  - 같은 그룹 내 멤버는 서로 다른 팀으로 분리
  - 충돌 발생 시:
    - formatted_must_link_groups > formatted_cannot_link_groups 우선순위로 처리
    - 불가능한 경우 reasoning에 명확히 설명

---

#### 2. 가중치 분산 규칙
- 동일 가중치는 가능한 한 **양 팀에 균등 분배**
- 그룹 단위 분배 이후에도 이 규칙 유지

---

#### 3. 대체 규칙 (Fallback)
- 특정 가중치가 한 팀에 몰릴 경우:
  - 가장 가까운 가중치로 대체하여 분산
- 단, 그룹 제약을 절대 깨지 말 것

---

#### 4. 금지 사항
- 단순 greedy (합계 기준) 분배 금지
- 극단적 분리 (저점/고점 몰림) 금지
- 그룹 제약 위반 금지

---

### 추천 접근 방식

1. formatted_must_link_groups 기반으로 멤버를 묶어 super node 생성
2. 가중치 기준 그룹화
3. 그룹 단위 교차 분배 (alternating)
4. formatted_cannot_link_groups 제약 체크 및 조정
5. 합 차이 최소화를 위한 최소 swap 수행

---

### 피드백 반영 규칙

- feedback이 존재하는 경우:
  - 기존 문제점을 분석
  - 제약 조건을 유지하면서 **최소 변경으로 개선**
- feedback이 없는 경우:
  - 기본 로직으로 최적 결과 생성

---

### 추가 요구사항

- 모든 멤버는 반드시 하나의 팀에만 속해야 한다
- 두 팀의 인원 수는 가능한 균형 유지
- 각 팀 내부 순서는 **완전히 랜덤 셔플**

---

### 출력 형식 (반드시 준수)

- team_a: list[str]
- team_b: list[str]
- score_diff: int
- reason: str (선택, 제약 충돌 또는 주요 판단 근거 설명)

---

### 최종 지침

- 항상 **분포 균형 > 합계 균형** 우선
- **그룹 제약은 절대 위반하지 말 것**
- 문제를 단순 분배가 아닌 **제약 기반 최적화 문제**로 접근하라
    """