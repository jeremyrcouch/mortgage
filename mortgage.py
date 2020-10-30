from dataclasses import dataclass
from matplotlib import pyplot as plt
import pandas as pd
import streamlit as st


def monthly_payment(amount: float, rate: float, term: int) -> float:
    return (amount*(rate*(1 + rate)**term)) / (((1 + rate)**term) - 1)


def build_am_table(term: int, amount: float, rate: float, total_payment: float) -> pd.DataFrame:
    months = [m for m in range(1, term + 1)]
    interests = [amount*rate]
    principals = [total_payment - interests[0]]
    balances = [amount - principals[0]]
    for _ in months[1:]:
        interests.append(max(0, balances[-1]*rate))
        principals.append(max(0, min(balances[-1] - interests[-1], total_payment - interests[-1])))
        newbal = balances[-1] - principals[-1]
        newbal = newbal if newbal > 1 else 0
        balances.append(max(0, newbal))
        
    am_table = pd.DataFrame({
        'month': months,
        'interest': interests,
        'principal': principals,
        'balance': balances
    })
    
    return am_table


@dataclass
class mortgage:
    term: int
    rate: float
    sale_price: float = None
    dp_dollars: float = None
    dp_percent: float = None
    loan_amount: float = None
    insurance: float = 0.0
    taxes: float = 0.0
    add_payment: float = 0.0
    payoff_months: int = None
    closing_costs: float = 0.0
    name: str = ''
    pmi_amount: float = 0.0
    pmi_ltv: float = 80.0

    def __post_init__(self):
        if (((self.loan_amount is None) or (self.loan_amount < 1))
             and ((self.sale_price is None) or (self.sale_price < 1))):
            raise ValueError('Sale price or loan amount must be defined and >= $1.')
        elif ((self.pmi_amount is not None) and (self.pmi_amount > 0)
              and ((self.sale_price is None) or (self.sale_price < 1))):
            raise ValueError('If there is PMI, the sale price must be defined to calculate LTV.')
        # if loan amount is defined, use it
        elif (self.loan_amount is not None) and (self.loan_amount >= 1):
            if (self.dp_dollars is None) and (self.dp_percent is None):
                self.dp_dollars = 0
                self.dp_percent = 0.0
            elif self.dp_dollars is not None:
                self.dp_percent = (self.dp_dollars/(self.loan_amount + self.dp_dollars))*100
            else:
                self.dp_dollars = ((self.dp_percent/100)*self.loan_amount)/(1 - (self.dp_percent/100))
            self.sale_price = self.loan_amount + self.dp_dollars
        # otherwise, use sale price
        else:
            if (self.dp_dollars is None) and (self.dp_percent is None):
                self.dp_dollars = 0
                self.dp_percent = 0.0
            elif self.dp_dollars is not None:
                self.dp_percent = (self.dp_dollars/self.sale_price)*100
            else:
                self.dp_dollars = self.sale_price*(self.dp_percent/100)
            self.loan_amount = self.sale_price - self.dp_dollars

        if self.insurance is None: self.insurance = 0.0
        if self.taxes is None: self.taxes = 0.0
        if self.add_payment is None: self.add_payment = 0.0
        if self.closing_costs is None: self.closing_costs = 0.0
        if self.name is None: self.name = ''
        if self.pmi_amount is None: self.pmi_amount = 0.0
        if self.pmi_ltv is None: self.pmi_ltv = 80.0
        
        self.c_rate = self.rate/(100*12)
        self.payoff = self.payoff_months if self.payoff_months is not None else self.term
        self.base_payment = monthly_payment(self.loan_amount, self.c_rate, self.term)
        self.piti_payment = self.base_payment + self.insurance/12 + self.taxes/12
        self.payment = self.base_payment + self.add_payment
        self.am_table_base = build_am_table(self.term, self.loan_amount, self.c_rate, self.base_payment)
        self.am_table = build_am_table(self.term, self.loan_amount, self.c_rate, self.payment)
        self.interest_paid_base = self.am_table_base.loc[self.am_table_base['month'] <= self.payoff,
                                                         'interest'].sum()
        self.interest_paid = self.am_table.loc[self.am_table['month'] <= self.payoff,
                                               'interest'].sum()
        self.interest_saved = self.interest_paid_base - self.interest_paid
        
        if self.pmi_amount <= 0: self.pmi_drop = 0
        else:
            am_with_ltv = self.am_table.copy()
            am_with_ltv['ltv'] = am_with_ltv.loc[:, 'balance']/self.sale_price
            self.pmi_drop = am_with_ltv.loc[am_with_ltv['ltv'] < (self.pmi_ltv/100), 'month'].min()
        self.pmi_total_cost = self.pmi_amount*self.pmi_drop
        self.finance_costs = self.interest_paid + self.closing_costs + self.pmi_total_cost
        
        self.months_payoff_by_payment = self.am_table.loc[self.am_table['balance'] > 0, 'month'].max()
        self.balance_at_payoff = 0
        self.payoff_reason = 'Payments'
        if self.months_payoff_by_payment > self.payoff:
            self.balance_at_payoff = self.am_table.loc[self.am_table['month'] == self.payoff, 'balance'].values[0]
            self.payoff_reason = 'Sale/Paid Off'
        self.payoff_month = min(self.months_payoff_by_payment, self.payoff)
        self.cash_to_close = self.dp_dollars + self.closing_costs
        
    def summary(self):
        values = [
            ('Loan Amount', '${:,.0f}'.format(self.loan_amount)),
            ('Down Payment', '${:,.0f}'.format(self.dp_dollars)),
            ('Term [months]', '{:.0f}'.format(self.term)),
            ('Rate [%]', '{:.3f}'.format(self.rate)),
            ('Payment', '${:,.0f}'.format(self.base_payment)),
            ('PITI Payment', '${:,.0f}'.format(self.piti_payment)),
            ('PMI Amount', '${:,.0f}'.format(self.pmi_amount)),
            ('Additional Payment', '${:,.0f}'.format(self.add_payment)),
            ('Total Payment', '${:,.0f}'.format(self.piti_payment + self.add_payment + self.pmi_amount)),
            ('PMI Drops Off At Month', '{:.0f}'.format(self.pmi_drop)),
            ('Payoff [months]', '{:.0f}'.format(self.payoff_month)),
            ('Balance at Payoff', '${:,.0f}'.format(self.balance_at_payoff)),
            ('Payoff Reason', self.payoff_reason),
            ('Interest Paid', '${:,.0f}'.format(self.interest_paid)),
            ('Interest Saved from Added Payments', '${:,.0f}'.format(self.interest_saved)),
            ('Closing Costs', '${:,.0f}'.format(self.closing_costs)),
            ('Cash To Close', '${:,.0f}'.format(self.cash_to_close)),
            ('Total Finance Costs', '${:,.0f}'.format(self.finance_costs))
        ]
        table = pd.DataFrame({
            'text': [v[0] for v in values],
            'values': [v[1] for v in values]
        })
        table = table.set_index('text')
        table.index.name = ''
        table = table.rename(columns={'values': self.name})
        return table
    
    def __repr__(self):
        return(str(self.summary()))
    
    def plot(self):
        fig, ax1 = plt.subplots()
        ax1.plot(
            [0] + self.am_table['month'].tolist(),
            [self.loan_amount] + self.am_table['balance'].tolist(),
            'b-', label='Balance'
        )
        ax1.set_ylabel('$\nBalance')
        ax1.set_xlabel('Month')
        ax2 = ax1.twinx()
        ax2.plot(
            self.am_table.loc[self.am_table['interest'] > 0, 'month'],
            self.am_table.loc[self.am_table['interest'] > 0, 'interest'],
            'r-', label='Interest'
        )
        ax2.plot(
            self.am_table.loc[self.am_table['principal'] > 0, 'month'],
            self.am_table.loc[self.am_table['principal'] > 0, 'principal'],
            'g-', label='Principal'
        )
        ax2.set_ylabel('$\nInterest\nPrincipal')
        _ = fig.legend()
        return fig


def compare_mortgages(inputs: pd.DataFrame) -> pd.DataFrame:
    """"""
    inputs = inputs.where(pd.notnull(inputs), None)
    table = None
    for i in range(len(inputs)):
        row = inputs.iloc[i, :].to_dict()
        temp = mortgage(**row)

        if table is None:
            table = temp.summary()
        else:
            table_add = temp.summary()
            table = pd.concat([table, table_add], axis=1, sort=False)
            
    return table


st.title('Mortgage Summary')
st.write('Fill out mortgage info in the sidebar to the left.')

st.sidebar.subheader('Mortgage Info')
name = st.sidebar.text_input(
    'Name',
    value='Option 1'
)
term = st.sidebar.number_input(
    'Term [months]',
    min_value=1,
    max_value=480,
    value=360,
    step=1
)
rate = st.sidebar.number_input(
    'Rate [%]',
    min_value=0.0,
    max_value=100.0,
    value=3.0,
    step=0.001
)
sale_amt_select = st.sidebar.radio(
    'Sale Price or Loan Amount',
    ['Sale Price', 'Loan Amount']
)
if sale_amt_select == 'Sale Price':
    sale_price = st.sidebar.number_input(
        'Sale Price [$]',
        min_value=0.0,
        max_value=10000000.0,
        value=300000.0,
        step=0.01
    )
elif sale_amt_select == 'Loan Amount':
    loan_amount = st.sidebar.number_input(
        'Loan Amount [$]',
        min_value=0.0,
        max_value=10000000.0,
        value=240000.0,
        step=0.01
    )
dp_select = st.sidebar.radio(
    'Down Payment Option',
    ['Dollars', 'Percent']
)
if dp_select == 'Dollars':
    dp_dollars = st.sidebar.number_input(
        'Down Payment [$]',
        min_value=0.0,
        max_value=10000000.0,
        value=60000.0,
        step=0.01
    )
elif dp_select == 'Percent':
    dp_percent = st.sidebar.number_input(
        'Down Payment [%]',
        min_value=0.0,
        max_value=100.0,
        value=20.0,
        step=0.01
    )
insurance = st.sidebar.number_input(
    'Insurance (annual) [$]',
    min_value=0.0,
    max_value=1000000.0,
    value=0.0,
    step=0.01
)
taxes = st.sidebar.number_input(
    'Taxes (annual) [$]',
    min_value=0.0,
    max_value=1000000.0,
    value=0.0,
    step=0.01
)
add_payment = st.sidebar.number_input(
    'Additional Monthly Payment to Principal [$]',
    min_value=0.0,
    max_value=1000000.0,
    value=0.0,
    step=0.01
)
payoff_months = st.sidebar.number_input(
    'Payoff At Month',
    min_value=0,
    max_value=480,
    value=0,
    step=1
)
closing_costs = st.sidebar.number_input(
    'Closing Costs [$]',
    min_value=-100000.0,
    max_value=100000.0,
    value=0.0,
    step=0.01
)
pmi_amount = st.sidebar.number_input(
    'PMI Amount [$]',
    min_value=0.0,
    max_value=100000.0,
    value=0.0,
    step=0.01
)
pmi_ltv = st.sidebar.number_input(
    'PMI Drops Off at LTV [%]',
    min_value=0.0,
    max_value=100.0,
    value=80.0,
    step=0.01
)

if sale_amt_select == 'Sale Price':
    loan_amount = None
elif sale_amt_select == 'Loan Amount':
    sale_price = None
if dp_select == 'Dollars':
    dp_percent = None
elif dp_select == 'Percent':
    dp_dollars = None
if payoff_months < 1: payoff_months = None

mort = mortgage(
    term=term,
    rate=rate,
    sale_price=sale_price,
    dp_dollars=dp_dollars,
    dp_percent=dp_percent,
    loan_amount=loan_amount,
    insurance=insurance,
    taxes=taxes,
    payoff_months=payoff_months,
    add_payment=add_payment,
    closing_costs=closing_costs,
    pmi_amount=pmi_amount,
    pmi_ltv=pmi_ltv,
    name=name
)

st.text(mort)

st.title('Mortgage Comparison')
inputs_raw = st.file_uploader('Upload a file:', type=['csv'])
if inputs_raw is not None:
    inputs = pd.read_csv(inputs_raw)
    table = compare_mortgages(inputs)
    st.dataframe(table, width=600, height=900)

st.write('Uploaded file should have these headers with the noted requirements:')
upload_explain = pd.DataFrame({
    'name': ['', '30 year']
    'sale_price': ['$', 300000]
    'dp_dollars': ['$', 60000]
    'dp_percent': ['%', 20]
    'loan_amount': ['$', 240000]
    'term': ['months', 360]
    'rate': ['%', 2.75]
    'insurance': ['$ - annual', 1000]
    'taxes': ['$ - annual', 4000]
    'add_payment': ['$ - monthly', 100]
    'payoff_months': ['months', 120]
    'closing_costs': ['$', 2200]
    'pmi_amount': ['$ - monthly', 75]
    'pmi_ltv': ['%', 80]
}, index=['units', 'example'])
st.dataframe(upload_explain, width=900)