from app.agent.router import decide_routing, RouteType
from app.schemas.agent import QueryIntent, AmbiguityCheck


def _decide(intent, secondary=None, ambiguity=None, entities=None, query=""):
    return decide_routing(
        intent=intent,
        secondary_intents=secondary or [],
        ambiguity=ambiguity or AmbiguityCheck(),
        entities=entities or {},
        query=query,
    )


def test_c1_routes_to_get_course_info():
    rd = _decide(QueryIntent.COURSE_DISCOVERY, query="What courses do you offer?")
    assert rd.route == RouteType.STRUCTURED_TOOL
    assert rd.tool_name == "get_course_info"


def test_c2_routes_to_get_course_info():
    rd = _decide(QueryIntent.COURSE_DETAILS, query="Tell me about PERC Champion")
    assert rd.route == RouteType.STRUCTURED_TOOL
    assert rd.tool_name == "get_course_info"


def test_c3_routes_to_get_fee():
    rd = _decide(QueryIntent.FEES_PRICING, query="How much is NEET UG?")
    assert rd.route == RouteType.STRUCTURED_TOOL
    assert rd.tool_name == "get_fee"


def test_c4_routes_to_get_eligibility():
    rd = _decide(QueryIntent.ELIGIBILITY, query="Who can join NEET Foundation?")
    assert rd.route == RouteType.STRUCTURED_TOOL
    assert rd.tool_name == "get_eligibility"


def test_c5_routes_to_get_branch_info():
    rd = _decide(QueryIntent.BRANCH_LOCATION, query="Where is PERC located?")
    assert rd.route == RouteType.STRUCTURED_TOOL
    assert rd.tool_name == "get_branch_info"


def test_c6_routes_to_get_admission_steps():
    rd = _decide(QueryIntent.ADMISSION_PROCESS, query="How do I apply?")
    assert rd.route == RouteType.STRUCTURED_TOOL
    assert rd.tool_name == "get_admission_steps"


def test_c9_general_vs_live():
    rd_general = _decide(QueryIntent.AVAILABILITY_STATUS, query="Do you have evening batches?")
    assert rd_general.route == RouteType.STRUCTURED_TOOL
    assert rd_general.tool_name == "get_availability"

    rd_live = _decide(QueryIntent.AVAILABILITY_STATUS, query="Are admissions open right now?")
    assert rd_live.route == RouteType.STRUCTURED_TOOL
    assert rd_live.tool_name == "get_admission_status"


def test_rag_intents_route_to_rag():
    for intent in [QueryIntent.REQUIRED_DOCUMENTS, QueryIntent.POLICIES, QueryIntent.COMPARISON, QueryIntent.HOSTEL_ACCOMMODATION, QueryIntent.PLACEMENT_CAREER_OUTCOMES, QueryIntent.LANGUAGE_MEDIUM]:
        rd = _decide(intent, query="irrelevant")
        assert rd.route == RouteType.RAG


def test_multi_intent_decomposes():
    rd = _decide(QueryIntent.MULTI_INTENT, secondary=[QueryIntent.FEES_PRICING, QueryIntent.REQUIRED_DOCUMENTS], query="Fees and docs")
    assert rd.route == RouteType.MULTI_INTENT
    assert rd.sub_routes and len(rd.sub_routes) == 2
    assert rd.sub_routes[0].tool_name == "get_fee"
    assert rd.sub_routes[1].route == RouteType.RAG


def test_followup_resolved_and_unresolved():
    # resolved via secondary intent
    rd = _decide(QueryIntent.FOLLOW_UP_CONTEXTUAL, secondary=[QueryIntent.COURSE_DETAILS], query="What time are classes?")
    assert rd.route == RouteType.STRUCTURED_TOOL

    # unresolved -> clarification
    rd2 = _decide(QueryIntent.FOLLOW_UP_CONTEXTUAL, ambiguity=AmbiguityCheck(is_ambiguous=True), query="What time?")
    assert rd2.route == RouteType.CLARIFICATION


def test_ambiguous_and_grievance_and_out_of_scope():
    rd = _decide(QueryIntent.AMBIGUOUS_INCOMPLETE, ambiguity=AmbiguityCheck(is_ambiguous=True))
    assert rd.route == RouteType.CLARIFICATION

    rd2 = _decide(QueryIntent.GRIEVANCE_HUMAN_HANDOFF)
    assert rd2.route == RouteType.HUMAN_HANDOFF

    rd3 = _decide(QueryIntent.OUT_OF_SCOPE_ESCALATION)
    assert rd3.route == RouteType.SAFE_STOP


def test_missing_intent_defaults_safe_stop():
    rd = _decide(None)
    assert rd.route == RouteType.SAFE_STOP
