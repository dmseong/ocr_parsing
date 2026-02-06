import streamlit as st
import json
import pandas as pd
import sys
import os

# 통합 파서 (UnifiedOCRParser)
from parser import UnifiedOCRParser as OCRParser
PARSER_VERSION = "integrated_v6"

from boundingBoxSet import reconstruct_layout_from_data

# 페이지 설정
st.set_page_config(
    page_title="OCR Parser Dashboard",
    page_icon="📄",
    layout="wide"
)

# 타이틀 및 설명
st.title("📄 Hybrid OCR Parser Dashboard")
st.markdown(f"""
OCR JSON 데이터를 업로드하면 **파싱된 결과**를 확인하고, **직접 수정**할 수 있습니다.  
`Parser: {PARSER_VERSION}`
""")

# 사이드바: 파일 업로드 및 설정
with st.sidebar:
    st.header("📂 Input Data")
    uploaded_file = st.file_uploader("Upload OCR JSON file", type=["json"])
    
    st.divider()
    json_text = st.text_area("Or paste JSON text here:", height=200, placeholder="Paste your OCR JSON content here...")

# 데이터 로드 로직
input_data = None

if uploaded_file is not None:
    try:
        input_data = json.load(uploaded_file)
        st.sidebar.success(f"Loaded: {uploaded_file.name}")
    except json.JSONDecodeError:
        st.sidebar.error("Invalid JSON file")
elif json_text:
    try:
        input_data = json.loads(json_text)
        st.sidebar.success("Loaded from text input")
    except json.JSONDecodeError:
        st.sidebar.error("Invalid JSON text")

# 메인 로직
if input_data:
    # 현재 파일 ID 생성 (파일명 또는 내용 기반)
    current_file_id = None
    if uploaded_file:
        current_file_id = uploaded_file.name
    else:
        # 텍스트 입력의 경우 내용의 해시나 길이로 구분
        current_file_id = f"text_{len(json_text)}"
        
    # 이미 파싱된 파일인지 확인 (새로고침 시 재파싱 방지)
    last_file_id = st.session_state.get('last_file_id')
    
    # 1. 새로운 파일이면 자동 파싱
    if current_file_id != last_file_id:
        try:
            with st.spinner("Processing new file..."):
                parser = OCRParser()
                parsed_result = parser.parse(input_data)
                
                # Session State에 결과 및 파일 ID 저장
                st.session_state['parsed_result'] = parsed_result
                st.session_state['last_file_id'] = current_file_id
                
                # UI 갱신을 위해 rerun (선택사항, 데이터 에디터 갱신 보장)
                st.rerun()
                
        except Exception as e:
            st.error(f"Error during parsing: {str(e)}")
            st.exception(e)

# 결과 표시 및 편집
if 'parsed_result' in st.session_state:
    result = st.session_state['parsed_result']
    
    # === 신뢰도 및 검수 정보 표시 (항상 표시) ===
    confidence = result.get('_overall_confidence', 0)
    needs_review = result.get('_needs_review', False)
    review_priority = result.get('_review_priority', 'N/A')
    
    col_conf1, col_conf2, col_conf3 = st.columns(3)
    with col_conf1:
        # 신뢰도에 따른 색상
        if confidence >= 90:
            st.metric("🎯 신뢰도", f"{confidence}%", delta="정상", delta_color="normal")
        elif confidence >= 70:
            st.metric("🎯 신뢰도", f"{confidence}%", delta="확인 권장", delta_color="off")
        else:
            st.metric("🎯 신뢰도", f"{confidence}%", delta="검수 필요", delta_color="inverse")
    
    with col_conf2:
        if needs_review:
            st.error(f"⚠️ 검수 필요 ({review_priority})")
        else:
            st.success(f"✅ 검수 불요 ({review_priority})")
    
    with col_conf3:
        issues = result.get('_issues', []).copy()
        
        # [추가] 필드 간 값 중복 체크
        import itertools
        target_fields = [
            "vehicle_num", "ticket_id", 
            "total_weight", "tare_weight", "net_weight",
            "company", "issuer", "product", "phone", "date"
        ]
        
        field_values = {}
        for k, v in result.items():
            if k in target_fields and v and str(v).strip():
                field_values[k] = str(v).strip()
        
        for f1, f2 in itertools.combinations(field_values.keys(), 2):
            v1 = field_values[f1]
            v2 = field_values[f2]
            if v1 == v2:
                issues.append(f"값 중복 감지: '{f1}' 필드와 '{f2}' 필드의 값이 동일합니다 ('{v1}').")

        if issues:
            with st.expander(f"📋 감지된 문제 ({len(issues)}건)", expanded=True):
                for issue in issues:
                    st.warning(issue)
        else:
            st.info("문제 없음")
    
    st.divider()

    # [수정] 레이아웃 복원(2) : 실시간 중량 검증(1) 컬럼 분할
    col_layout, col_weight = st.columns([2, 1])

    # 오른쪽 (1): 실시간 중량 검증 컨테이너 확보
    with col_weight:
        weight_check_container = st.container()
    
    # 왼쪽 (2): 레이아웃 복원 시각화
    with col_layout:
        def has_bounding_box(data):
            """OCR 데이터에 boundingBox가 있는지 확인"""
            if isinstance(data, dict):
                if 'boundingBox' in data:
                    return True
                for value in data.values():
                    if has_bounding_box(value):
                        return True
            elif isinstance(data, list):
                for item in data:
                    if has_bounding_box(item):
                        return True
            return False
        
        if input_data and has_bounding_box(input_data):
            st.subheader("🗺️ 좌표 기반 레이아웃 복원")
            st.caption("OCR 좌표(boundingBox)를 기반으로 원본 문서의 배치를 복원합니다.")
            try:
                layout_text = reconstruct_layout_from_data(input_data)
                st.code(layout_text, language=None)
            except Exception as e:
                st.warning(f"레이아웃 복원 실패: {str(e)}")
        elif input_data:
            st.info("ℹ️ 이 데이터에는 boundingBox 정보가 없어 레이아웃 복원을 건너뜁니다.")
            
    st.divider()
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📝 Edit Results (Table)")
        st.caption("값을 더블 클릭하여 수정하세요.")
        
        # 딕셔너리를 DataFrame으로 변환 (보기 좋게 Transpose)
        # 메타 필드(_로 시작)는 제외
        display_result = {k: v for k, v in result.items() if not k.startswith('_')}
        df = pd.DataFrame(list(display_result.items()), columns=["Field", "Value"])
        
        # 수정 가능하도록 모든 값을 문자열로 변환 (None -> "")
        df["Value"] = df["Value"].apply(lambda x: "" if x is None else str(x))
        
        # Data Editor (수정 가능)
        edited_df = st.data_editor(
            df,
            column_config={
                "Field": st.column_config.TextColumn("Field Name", disabled=True), # 키는 수정 불가
                "Value": st.column_config.TextColumn("Extracted Value")
            },
            hide_index=True,
            width="stretch",
            num_rows="dynamic"
        )
        




    
    with col2:
        st.subheader("📋 JSON Output")
        st.caption("수정된 결과가 실시간으로 반영됩니다. 아래 코드를 복사하세요.")
        
        # 수정된 DataFrame을 다시 딕셔너리로 변환
        # pd.NA, np.nan 등을 None으로 변환하여 JSON 호환성 확보
        edited_df_clean = edited_df.replace({pd.NA: None}).where(pd.notnull(edited_df), None)
        edited_dict = dict(zip(edited_df_clean["Field"], edited_df_clean["Value"]))
        
        # JSON 포맷팅
        json_str = json.dumps(edited_dict, indent=4, ensure_ascii=False)
        
        # JSON 코드 블록 (복사 버튼 포함)
        st.code(json_str, language="json")
        
        # 다운로드 버튼
        st.download_button(
            label="💾 Download JSON",
            data=json_str,
            file_name="parsed_result.json",
            mime="application/json"
        )
            
    # --- GPS 지도 표시 (행 전체 너비 사용) ---
    gps_value = edited_dict.get("gps", "")
    if gps_value and gps_value.strip():
        st.divider()
        st.subheader("🗺️ GPS Location")
        
        try:
            # GPS 문자열을 딕셔너리로 파싱
            # 예: "{'latitude': 37.105317, 'longitude': 127.375673}"
            import ast
            gps_data = ast.literal_eval(gps_value)
            
            lat = gps_data.get('latitude')
            lon = gps_data.get('longitude')
            
            if lat is not None and lon is not None:
                # 지도용 DataFrame 생성
                map_df = pd.DataFrame({
                    'lat': [float(lat)],
                    'lon': [float(lon)]
                })
                
                st.caption(f"📍 위도: {lat}, 경도: {lon}")
                st.map(map_df, zoom=14)
            else:
                st.warning("GPS 데이터에 위도/경도 정보가 없습니다.")
        except Exception as e:
            st.error(f"GPS 데이터 파싱 오류: {str(e)}")
            
    # [이동됨] 실시간 중량 검증 로직 구현 및 번역
    # 위에서 생성한 weight_check_container에 내용을 채웁니다.
    if 'edited_df' in locals():
        with weight_check_container:
            st.subheader("⚖️ 실시간 중량 검증")
            
            # Helper: DataFrame에서 값 추출
            def _get_weight(df, field_name):
                try:
                    row = df[df['Field'] == field_name]
                    if not row.empty:
                        val = row.iloc[0]['Value']
                        if pd.isna(val) or val is None or str(val).strip() == "":
                            return None
                        return int(str(val).replace(',', '').strip())
                except (ValueError, TypeError):
                    return None
                return None

            total_w = _get_weight(edited_df, "total_weight")
            tare_w = _get_weight(edited_df, "tare_weight")
            net_w = _get_weight(edited_df, "net_weight")
            
            if total_w is not None and tare_w is not None:
                calc_net = total_w - tare_w
                st.info(f"🔢 계산된 실중량: **{calc_net:,} kg** ( = {total_w:,} - {tare_w:,} )")
                
                if net_w is not None:
                    if calc_net == net_w:
                        st.success(f"✅ 일치! 계산값({calc_net:,})과 추출값({net_w:,})이 동일합니다.")
                    else:
                        diff = net_w - calc_net
                        st.error(f"❌ 불일치! 추출값: {net_w:,} kg (차이: {diff:+,} kg)")
                else:
                    st.warning("⚠️ 테이블에 'net_weight' 값이 없습니다.")
            else:
                st.caption("'total_weight'와 'tare_weight' 값을 입력하면 검증 결과가 표시됩니다.")
            
            st.divider()


else:
    # 데이터가 없을 때 안내
    if not input_data:
        st.info("👈 왼쪽 사이드바에서 JSON 파일을 업로드하거나 붙여넣으세요.")

