"""
MES 전체 페이지 레지스트리
list.html에서 추출한 모든 페이지 정의
"""

MES_BASE_URL = "https://dmc.mescloud.net"

# 전체 페이지 레지스트리 (68개)
MES_PAGES = {
    # ===== 결재 =====
    "all_sign": {"category": "결재", "name": "검토/승인 처리", "folder_name": "검토승인_처리", "url": "/P75_ETC/AllSign.aspx"},
    "shape_sign": {"category": "결재", "name": "금형 수정/폐기 보고", "folder_name": "금형_수정폐기_보고", "url": "/P75_ETC/ShapeSign.aspx"},
    
    # ===== 수주 =====
    "order": {"category": "수주", "name": "수주 등록", "folder_name": "수주_등록", "url": "/P10_ORD/Order.aspx"},
    "order_end": {"category": "수주", "name": "수주 납품완료 처리", "folder_name": "수주_납품완료_처리", "url": "/P10_ORD/OrderEnd.aspx"},
    
    # ===== 자재 =====
    "balzu": {"category": "자재", "name": "발주 관리", "folder_name": "발주_관리", "url": "/P20_RSC/Balzu.aspx"},
    "rescin2": {"category": "자재", "name": "입고 관리", "folder_name": "입고_관리", "url": "/P20_RSC/Rescin2.aspx"},
    "resc_out": {"category": "자재", "name": "반품 관리", "folder_name": "반품_관리", "url": "/P20_RSC/RescOut.aspx"},
    "resc_move": {"category": "자재", "name": "이동 관리", "folder_name": "이동_관리", "url": "/P20_RSC/RescMove.aspx"},
    "resc_sell": {"category": "자재", "name": "판매 관리", "folder_name": "판매_관리", "url": "/P20_RSC/RescSell.aspx"},
    "scrap": {"category": "자재", "name": "스크랩수불 관리", "folder_name": "스크랩수불_관리", "url": "/P20_RSC/Scrap.aspx"},
    "resc_check": {"category": "자재", "name": "자재 수입검사 등록", "folder_name": "자재_수입검사_등록", "url": "/P20_RSC/RescCheck.aspx"},
    "resc_check_status": {"category": "자재", "name": "기간별 수입검사 현황", "folder_name": "기간별_수입검사_현황", "url": "/P20_RSC/RescCheckStatus.aspx"},
    "resc_comp": {"category": "자재", "name": "매입처원장", "folder_name": "매입처원장", "url": "/P20_RSC/RescComp.aspx"},
    "resc_status": {"category": "자재", "name": "자재 재고현황", "folder_name": "자재_재고현황", "url": "/P20_RSC/RescStatus.aspx"},
    "resc_status_all": {"category": "자재", "name": "전체 자재 재고현황", "folder_name": "전체_자재_재고현황", "url": "/P20_RSC/RescStatusAll.aspx"},
    "resc_hist": {"category": "자재", "name": "자재별 입출내역", "folder_name": "자재별_입출내역", "url": "/P20_RSC/RescHist.aspx"},
    "summ_resc": {"category": "자재", "name": "빌레트 수불현황", "folder_name": "빌레트_수불현황", "url": "/P20_RSC/SummResc.aspx"},
    "summ_scrap": {"category": "자재", "name": "스크랩 수불현황", "folder_name": "스크랩_수불현황", "url": "/P20_RSC/SummScrap.aspx"},
    
    # ===== 금형 =====
    "m_shape": {"category": "금형", "name": "금형번호 등록", "folder_name": "금형번호_등록", "url": "/P50_QLT/MShape.aspx"},
    "shape_bal": {"category": "금형", "name": "금형발주 등록", "folder_name": "금형발주_등록", "url": "/P50_QLT/ShapeBal.aspx"},
    "shape_inn": {"category": "금형", "name": "금형입고 등록", "folder_name": "금형입고_등록", "url": "/P50_QLT/ShapeINN.aspx"},
    "shape": {"category": "금형", "name": "금형 REV 관리", "folder_name": "금형_REV_관리", "url": "/P50_QLT/Shape.aspx"},
    "shape_hist": {"category": "금형", "name": "금형 이력현황", "folder_name": "금형_이력현황", "url": "/P50_QLT/ShapeHist.aspx"},
    "shape_man": {"category": "금형", "name": "금형 수정/폐기 등록", "folder_name": "금형_수정폐기_등록", "url": "/P50_QLT/ShapeMan.aspx"},
    
    # ===== 생산 =====
    "job": {"category": "생산", "name": "작업지시 등록", "folder_name": "작업지시_등록", "url": "/P30_PRO/Job.aspx"},
    "proc_res_shape": {"category": "생산", "name": "금형 투입 등록", "folder_name": "금형_투입_등록", "url": "/P30_PRO/ProcRes_Shape.aspx"},
    "proc_res_press": {"category": "생산", "name": "압출 결과등록", "folder_name": "압출_결과등록", "url": "/P30_PRO/ProcRes_Press.aspx"},
    "proc_res_heating": {"category": "생산", "name": "열처리 결과등록", "folder_name": "열처리_결과등록", "url": "/P30_PRO/ProcRes_Heating.aspx"},
    "proc_res_cutting": {"category": "생산", "name": "절단가공 결과등록", "folder_name": "절단가공_결과등록", "url": "/P30_PRO/ProcRes_Cutting.aspx"},
    "proc_res_mct": {"category": "생산", "name": "MCT가공 결과등록", "folder_name": "MCT가공_결과등록", "url": "/P30_PRO/ProcRes_MCT.aspx"},
    "proc_res_qc": {"category": "생산", "name": "QC검사 결과등록", "folder_name": "QC검사_결과등록", "url": "/P30_PRO/ProcRes_QC.aspx"},
    "goods_prt": {"category": "생산", "name": "제품식별표 출력", "folder_name": "제품식별표_출력", "url": "/P30_PRO/GoodsPrt.aspx"},
    "proc_status": {"category": "생산", "name": "공정이동 현황", "folder_name": "공정이동_현황", "url": "/P30_PRO/ProcStatus.aspx"},
    "proc_stock": {"category": "생산", "name": "공정별 재공현황", "folder_name": "공정별_재공현황", "url": "/P30_PRO/ProcStock.aspx"},
    "proc_goods_stock": {"category": "생산", "name": "제품별 재공집계", "folder_name": "제품별_재공집계", "url": "/P30_PRO/ProcGoodsStock.aspx"},
    
    # ===== 품질 =====
    "goods_out_ret": {"category": "품질", "name": "반품 등록", "folder_name": "반품_등록", "url": "/P40_GDS/GoodsOutRet.aspx"},
    "goods_out_ret_status": {"category": "품질", "name": "기간별 제품반품 현황", "folder_name": "기간별_제품반품_현황", "url": "/P40_GDS/GoodsOutRetStatus.aspx"},
    "out_ret_check": {"category": "품질", "name": "반품 품질검사 등록", "folder_name": "반품_품질검사_등록", "url": "/P40_GDS/OutRetCheck.aspx"},
    "b_type_graph": {"category": "품질", "name": "불량유형별 분석", "folder_name": "불량유형별_분석", "url": "/P75_ETC/BTypeGraph.aspx"},
    
    # ===== 외주 =====
    "outside_bal": {"category": "외주", "name": "외주 발주등록", "folder_name": "외주_발주등록", "url": "/P30_PRO/OutsideBal.aspx"},
    "outside_out": {"category": "외주", "name": "외주 출고등록", "folder_name": "외주_출고등록", "url": "/P30_PRO/OutsideOut.aspx"},
    "outside_out_in": {"category": "외주", "name": "외주 입고등록", "folder_name": "외주_입고등록", "url": "/P30_PRO/OutsideOutIN.aspx"},
    "outside_in2_sts": {"category": "외주", "name": "기간별 외주입고 현황", "folder_name": "기간별_외주입고_현황", "url": "/P30_PRO/OutsideIN2Sts.aspx"},
    "outside_in2_comp": {"category": "외주", "name": "외주처원장", "folder_name": "외주처원장", "url": "/P30_PRO/OutsideIN2Comp.aspx"},
    "outside_stock": {"category": "외주", "name": "외주처별 재고현황", "folder_name": "외주처별_재고현황", "url": "/P30_PRO/OutsideStock.aspx"},
    
    # ===== 외주생산 =====
    "out_press_bal": {"category": "외주생산", "name": "외주생산 발주등록", "folder_name": "외주생산_발주등록", "url": "/P30_PRO/OutPressBal.aspx"},
    "out_press_in": {"category": "외주생산", "name": "외주생산 입고등록", "folder_name": "외주생산_입고등록", "url": "/P30_PRO/OutPressIN.aspx"},
    
    # ===== 제품 =====
    "out": {"category": "제품", "name": "출고 등록", "folder_name": "출고_등록", "url": "/P40_GDS/Out.aspx"},
    "goods_out_status": {"category": "제품", "name": "기간별 제품출고 현황", "folder_name": "기간별_제품출고_현황", "url": "/P40_GDS/GoodsOutStatus.aspx"},
    "out_price": {"category": "제품", "name": "출고단가 조정", "folder_name": "출고단가_조정", "url": "/P40_GDS/OutPrice.aspx"},
    "goods_out_comp": {"category": "제품", "name": "매출처원장", "folder_name": "매출처원장", "url": "/P40_GDS/GoodsOutComp.aspx"},
    "goods_status": {"category": "제품", "name": "제품 재고현황", "folder_name": "제품_재고현황", "url": "/P40_GDS/GoodsStatus.aspx"},
    "goods_hist": {"category": "제품", "name": "제품별 입출내역", "folder_name": "제품별_입출내역", "url": "/P40_GDS/GoodsHist.aspx"},
    "trace_lot": {"category": "제품", "name": "Lot No. 추적", "folder_name": "LotNo_추적", "url": "/P50_QLT/TraceLOT.aspx"},
    
    # ===== 리포트 =====
    "rpt_press": {"category": "리포트", "name": "압출 일보", "folder_name": "압출_일보", "url": "/P60_SUM/RptPress.aspx"},
    "rpt_heating": {"category": "리포트", "name": "열처리 일보", "folder_name": "열처리_일보", "url": "/P60_SUM/RptHeating.aspx"},
    "rpt_2nd_cut": {"category": "리포트", "name": "절단 일보", "folder_name": "절단_일보", "url": "/P60_SUM/Rpt2ndCut.aspx"},
    "rpt_mct": {"category": "리포트", "name": "가공 일보", "folder_name": "가공_일보", "url": "/P60_SUM/RptMCT.aspx"},
    "stock_sum": {"category": "리포트", "name": "재고조사 현황", "folder_name": "재고조사_현황", "url": "/P60_SUM/StockSum.aspx"},
    "p_rate_mon": {"category": "리포트", "name": "월별 생산성현황", "folder_name": "월별_생산성현황", "url": "/P60_SUM/PRateMon.aspx"},
    
    # ===== 분석통계 =====
    "cust_rank": {"category": "분석통계", "name": "거래처별 매출분석", "folder_name": "거래처별_매출분석", "url": "/P60_SUM/CustRank.aspx"},
    "goods_rank": {"category": "분석통계", "name": "제품별 매출분석", "folder_name": "제품별_매출분석", "url": "/P60_SUM/GoodsRank.aspx"},
    "delivery_anal": {"category": "분석통계", "name": "납기준수율 분석", "folder_name": "납기준수율_분석", "url": "/P60_SUM/DeliveryAnal.aspx"},
    
    # ===== 재고 =====
    "resc_base": {"category": "재고", "name": "자재 기초재고 수정", "folder_name": "자재_기초재고_수정", "url": "/P70_BAS/RescBase.aspx"},
    "goods_base": {"category": "재고", "name": "제품 기초재고 수정", "folder_name": "제품_기초재고_수정", "url": "/P70_BAS/GoodsBase.aspx"},
    "resc_stock_adj": {"category": "재고", "name": "자재 재고조정 등록", "folder_name": "자재_재고조정_등록", "url": "/P70_BAS/RescStock.aspx"},
    "goods_stock_adj": {"category": "재고", "name": "제품 재고조정 등록", "folder_name": "제품_재고조정_등록", "url": "/P70_BAS/GoodsStock.aspx"},
    
    # ===== 기초 =====
    "cust": {"category": "기초", "name": "매출처 등록", "folder_name": "매출처_등록", "url": "/P70_BAS/Cust.aspx"},
    "buy": {"category": "기초", "name": "매입처 등록", "folder_name": "매입처_등록", "url": "/P70_BAS/Buy.aspx"},
    "outside": {"category": "기초", "name": "외주처 등록", "folder_name": "외주처_등록", "url": "/P70_BAS/Outside.aspx"},
    "maker": {"category": "기초", "name": "제작처 등록", "folder_name": "제작처_등록", "url": "/P70_BAS/Maker.aspx"},
    "resc": {"category": "기초", "name": "자재 등록", "folder_name": "자재_등록", "url": "/P70_BAS/Resc.aspx"},
    "goods": {"category": "기초", "name": "제품 등록", "folder_name": "제품_등록", "url": "/P70_BAS/Goods.aspx"},
    "plan": {"category": "기초", "name": "KPI지표 계획 등록", "folder_name": "KPI지표_계획_등록", "url": "/P70_BAS/Plan.aspx"},
    
    # ===== 참조코드 =====
    "sector": {"category": "참조코드", "name": "제품업종 등록", "folder_name": "제품업종_등록", "url": "/P70_BAS/Sector.aspx"},
    "shape_ref": {"category": "참조코드", "name": "제품형상 등록", "folder_name": "제품형상_등록", "url": "/P70_BAS/Shape.aspx"},
    "color": {"category": "참조코드", "name": "색상 등록", "folder_name": "색상_등록", "url": "/P90_SYS/Color.aspx"},
    "quenching": {"category": "참조코드", "name": "퀜칭 등록", "folder_name": "퀜칭_등록", "url": "/P90_SYS/Quenching.aspx"},
    "p_type": {"category": "참조코드", "name": "양산구분 등록", "folder_name": "양산구분_등록", "url": "/P90_SYS/PType.aspx"},
    "cutter": {"category": "참조코드", "name": "절단기 등록", "folder_name": "절단기_등록", "url": "/P90_SYS/Cutter.aspx"},
    "pallet": {"category": "참조코드", "name": "파렛트 등록", "folder_name": "파렛트_등록", "url": "/P90_SYS/Pallet.aspx"},
    "scrap_kind": {"category": "참조코드", "name": "스크랩종류 등록", "folder_name": "스크랩종류_등록", "url": "/P75_ETC/ScrapKind.aspx"},
    "scrap_resc": {"category": "참조코드", "name": "스크랩품목 등록", "folder_name": "스크랩품목_등록", "url": "/P75_ETC/ScrapResc.aspx"},
    
    # ===== 시스템 =====
    "fact": {"category": "시스템", "name": "공장 등록", "folder_name": "공장_등록", "url": "/P90_SYS/Fact.aspx"},
    "dept": {"category": "시스템", "name": "부서 등록", "folder_name": "부서_등록", "url": "/P90_SYS/Dept.aspx"},
    "zik": {"category": "시스템", "name": "직위 등록", "folder_name": "직위_등록", "url": "/P90_SYS/Zik.aspx"},
    "user": {"category": "시스템", "name": "사원 등록", "folder_name": "사원_등록", "url": "/P90_SYS/User.aspx"},
    "app_line": {"category": "시스템", "name": "결재선 설정", "folder_name": "결재선_설정", "url": "/P90_SYS/AppLine.aspx"},
    "m_group": {"category": "시스템", "name": "메뉴모음 등록", "folder_name": "메뉴모음_등록", "url": "/P90_SYS/MGroup.aspx"},
    "m_user": {"category": "시스템", "name": "사원메뉴 설정", "folder_name": "사원메뉴_설정", "url": "/P90_SYS/MUser.aspx"},
    "acc_log": {"category": "시스템", "name": "접속로그 현황", "folder_name": "접속로그_현황", "url": "/P90_SYS/AccLog.aspx"},
}


def get_pages_by_category(category: str) -> dict:
    """카테고리별 페이지 필터링"""
    return {k: v for k, v in MES_PAGES.items() if v["category"] == category}


def get_all_urls() -> list[str]:
    """모든 페이지 URL 반환"""
    return [f"{MES_BASE_URL}{p['url']}" for p in MES_PAGES.values()]


if __name__ == "__main__":
    print(f"총 {len(MES_PAGES)}개 페이지 등록됨")
    
    # 카테고리별 통계
    categories = {}
    for p in MES_PAGES.values():
        cat = p["category"]
        categories[cat] = categories.get(cat, 0) + 1
    
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}개")
