## ORDER MANAGEMENT (TREE VIEW)

This is a note of which fields are visible to which department

- **Payment Term** field All departments can view except operations.

- **CREDIT INFO** page All departments can view except operations.

- **ORDER PRICING INFO** page

  - **Margin** field is visible to only **Trading**
  - **Spot and Forward Rates** is visible to **Accounting**, **Trading**, **Finance**
    and **Credit Control**

- **DECLINE HISTORY** page All departments can view except **Operations**.

- **LOADING HISTORY** page

  - **Hedge Status** field is visible to al departments except **Operations** and
    **Marketing**.

- **OTHER INFO** page
  - **Hedge Info** page is visible to all departments except **Operations** and
    **Marketing**.

## Insight into SOS State

There are 4 states for order's **state**

1. Fully Invoiced SO
2. Partially Invoiced SO
3. Fully Validated SO
4. Partially Invoiced SO

Steps for determing SO state:

1. **Fully Invoiced** if all loads in the SO have been invoiced
2. **Fully Validated** if all loads in the SO have validated as SOs
3. **Partially Invoiced** if at least one of the loads in the order has been invoiced
4. **Partially Validated** if at least one of the loads in the order has been validated
   The order above is maintain when checking for the s
